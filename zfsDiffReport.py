#!/usr/bin/env python3

import logging
import argparse
import subprocess
import os
from pwd import getpwnam
import hashlib
from pathlib import Path
import re

DESCRIPTION = """
zfsDiffReport.py generates a report text file from the ZFS diff of a
given volume's two last snapshots containing a given identifier.

The script is intended to be used as companion to zfs-auto-snapshot.
I use it to check my weekly snapshots for unintended file deletions.
"""

EPILOG = """
And that's how you report a ZFS diff.
"""


def getArgs():
    parser = argparse.ArgumentParser(description=DESCRIPTION, epilog=EPILOG)
    parser.add_argument("volume", nargs="+",
                        help="observed ZFS volume(s) e.g.: 'ZPOOL/ZFSVOL'")
    parser.add_argument("-s", "--snapshotkeys", nargs="*", action="append",
                        default=[],
                        help="snapshot keywords e.g.: 'zas_w-utc-', \
                        no keyword: diff latest snapshots, \
                        one keyword: diff latest snapshots containing \
                        the keyword, two keywords: diff latest \
                        snapshots each containing given keywords \
                        respectively")
    parser.add_argument("-o", "--outdir", default=".",
                        help="report file output directory")
    parser.add_argument("-f", "--filename", nargs="?", const=" ",
                        help="if not set each volume diff is written to a \
                        separate file. if set all volume diffs are written \
                        to it, if empty all reports are written to stdout, \
                        if not set one report per volume is created")
    parser.add_argument("--outfilesuffix", default="_zfsDiffReport.txt",
                        help="suffix for report text file; \
                        default: '_zfsDiffReport.txt'")
    parser.add_argument("-u", "--user",
                        help="user for output file e.g.: 'user'")
    parser.add_argument("-e", "--exclude", action="append",
                        help="multiple definitions possible; diff lines \
                        containing an exclude keyword will be omitted \
                        e.g. '.git'")
    parser.add_argument("-r", "--reduce", action="store_true",
                        help="ZFS lists a file that is deleted and \
                        (re)created between snapshots with - and +; omit \
                        those lines when the files' checksums match")
    parser.add_argument("--zfsbinary", default="zfs",
                        help="path to ZFS binary; default: 'zfs'")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    return parser.parse_args()


def handleLogging(args):
    if args.debug:
        FORMAT = "%(levelname)-8s %(asctime)-15s %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=FORMAT)
    elif args.quiet:
        FORMAT = "%(levelname)-8s %(message)s"
        logging.basicConfig(level=logging.CRITICAL, format=FORMAT)
    else:
        FORMAT = "%(message)s"
        logging.basicConfig(level=logging.INFO, format=FORMAT)


# Thanks to https://github.com/hungrywolf27 for that routine
# https://github.com/schwerpunkt/zfsDiffReport.py/issues/6
def decode_octal(encoded):
    # Match b'\\0xxx'
    for oct_char in (c for c in re.findall(b'\\\\0\d{3}', encoded)):
        # Figured out through hours of trial and error:
        # Strip out '\0' to leave b'xxx' of octal number
        #    br'' means raw bytes (\ not treated as escape)
        #    Note that it's impossible to create b'\' in Python;
        #    can't end with a single backslash.
        myoct = oct_char.replace(br'\0', b'')
        # Convert this from octal to an integer
        myint = int(myoct, 8)
        encoded = encoded.replace(oct_char, bytes([myint]))
    return encoded


def getSnapshots(volume, snapshotkeys):
    logging.info("Get snapshot list for {}".format(volume))
    process = subprocess.Popen(
        ["zfs list -t snapshot -o name -s creation -r {}".format(volume)],
        shell=True, stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    zfssnapshots = stdout.decode("utf-8").splitlines()

    tmpZfsSnapshots = zfssnapshots
    if len(snapshotkeys) > 0:
        logging.debug("Filter latest snapshots containing {}".format(
            snapshotkeys[0]))
        tmpZfsSnapshots = list(
            filter(lambda x: snapshotkeys[0] in x, zfssnapshots))
    # if two keys are given, filter by second key excluding the previous result
    # and push latest from previous filtering to the end
    # (they will be sorted chronologically later)
    if len(snapshotkeys) > 1 and len(tmpZfsSnapshots) > 0:
        logging.debug("Filter latest snapshots containing {}".format(
            snapshotkeys[1]))
        tmpZfsSnapshots = list(
            filter(lambda x: snapshotkeys[1] in x and
                   not tmpZfsSnapshots[-1] in x,
                   zfssnapshots)) + [tmpZfsSnapshots[-1]]

    enoughSnapshots = True if len(tmpZfsSnapshots) > 1 else False
    snapshot1 = tmpZfsSnapshots[-2] if enoughSnapshots else ""
    snapshot2 = tmpZfsSnapshots[-1] if enoughSnapshots else ""
    if not enoughSnapshots:
        logging.critical("ERROR: Not enough snapshots in volume {} \
for given snapshot keys {}".format(volume,
                                   snapshotkeys if len(snapshotkeys) > 0
                                   else ""))

    # sort snapshots chronologically
    if ((enoughSnapshots) and
       (zfssnapshots.index(snapshot1) > zfssnapshots.index(snapshot2))):
        tmpSnapshot = snapshot2
        snapshot2 = snapshot1
        snapshot1 = tmpSnapshot

    return enoughSnapshots, snapshot1, snapshot2


def getSortedDiffLines(snapshot1, snapshot2):
    logging.info("Create zfs diff of snapshots {} and {}".format(
        snapshot1, snapshot2))
    process = subprocess.Popen(["zfs diff {} {}".format(
        snapshot1, snapshot2)], shell=True, stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    
    # decode octal values created by zfs diff
    difflines = decode_octal(stdout)
    difflines = difflines.decode("utf-8")

    difflines = difflines.splitlines()

    # sorting difflines by second column
    return sorted(difflines, key=lambda x: x.split()[1])


def getFilteredDifflines(difflines, excludes):
    if excludes:
            logging.info("Exclude lines containing '{}'".format(
                " or ".join(excludes)))
            difflines = list(filter(
                lambda x: not any(f in x for f in excludes), difflines))
    return difflines


def getHash(file):
    if Path(file).is_dir():
        return ""
    if not Path(file).is_file():
        return ""
    # code from : https://stackoverflow.com/q/3431825/#tab-top
    hash_alg = hashlib.sha1()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_alg.update(chunk)
    return hash_alg.hexdigest()


def getReducedDifflines(
  difflines,
  stripVolumePath,
  mountpoint,
  snapshot1,
  snapshot2):
    zfsstructure = "/.zfs/snapshot/"
    snapshot1 = mountpoint+zfsstructure+snapshot1.split("@")[1]
    snapshot2 = mountpoint+zfsstructure+snapshot2.split("@")[1]
    logging.debug("Reduce lines after hashing files from\n\
{} and\n{}\nstripVolumePath {}".format(
                      snapshot1, snapshot2, stripVolumePath))

    reduceddifflines = []
    mreduced = False
    for index, line in enumerate(difflines):
        # TODO write separate reduced line file maybe

        if mreduced:
            mreduced = False
            logging.debug("Reducing line {}".format(line))
            continue

        if line.startswith("M") and len(line) > 3:
            mfile = line.split("{}".format(mountpoint))[1]
            mhash1 = getHash(snapshot1+mfile)
            mhash2 = getHash(snapshot2+mfile)
            line = "{} {} {}".format(line, mhash1, mhash2)
            if mhash1 == mhash2:
                logging.debug("Reducing line {}".format(line))
                continue

        elif (index+1 < len(difflines) and
              ((line.startswith("-") and difflines[index+1].startswith("+")) or
               (line.startswith("+") and difflines[index+1].startswith("-")))):
            mfile = line.split("{}".format(mountpoint))[1]
            pfile = difflines[index+1].split("{}".format(mountpoint))[1]
            if mfile == pfile:
                mhash = getHash(snapshot1+mfile)
                phash = getHash(snapshot1+pfile)
                line = "{} {}".format(line, mhash)
                difflines[index+1] = "{} {}".format(difflines[index+1], phash)
                if mhash == phash:
                    logging.debug("Reducing line {}".format(line))
                    mreduced = True
                    continue

        if stripVolumePath:
            # strip mountpoint from paths
            line = line.replace(mountpoint, "", 1)
            # strip for zfs renames R
            line = line.replace(" -> {}".format(mountpoint), " -> ", 1)

        line = " ".join(line.split())

        reduceddifflines.append(line)

    return reduceddifflines


def writeReport(difflines, outdir, outfile, outfilesuffix, user):
    outpath = outdir+"/"+outfile+outfilesuffix
    logging.info("Write to {}".format(outpath))
    file = open(outpath, "w")
    file.write("\n".join(difflines))
    file.close()

    if user:
        logging.debug("Setting user for user {}".format(user))
        os.chown(outpath, getpwnam(user).pw_uid, getpwnam(user).pw_gid)


def main():
    args = getArgs()
    handleLogging(args)

    # convert snapshot keys to always be a list of strings and never
    # a list of lists containing strings
    # (happens when using multiple -s)
    if len(args.snapshotkeys) > 0:
        logging.debug("Converting snapshot keys to list of strings")
        snapshotkeys = []
        for argument in args.snapshotkeys:
            for key in argument:
                snapshotkeys.append(key)
        args.snapshotkeys = snapshotkeys

    # args check
    if len(args.snapshotkeys) > 2:
        logging.critical("ERROR: too many snapshotkeys given {} (max 2)".format(args.snapshotkeys))
        return

    try:
        if args.user:
            getpwnam(args.user)
    except KeyError:
        logging.critical("ERROR: Given user does not exist")
        return

    if os.geteuid() != 0:
        logging.warning("Warning: Root privileges are expected")

    if not Path(args.outdir).is_dir():
        logging.critical("ERROR: Output directory does not exist")
        return

    # remove volume duplicates
    volumes = list(set(args.volume))

    collecteddifflines = []
    errors = 0
    for volume in volumes:
        mountpoint = "/{}".format(volume)  # TODO get actual mountpoint
        getSnapshotsSuccess, snapshot1, snapshot2 = getSnapshots(
            volume,
            args.snapshotkeys)
        if not getSnapshotsSuccess:
            errors += 1
            continue

        difflines = getSortedDiffLines(snapshot1, snapshot2)
        difflines = getFilteredDifflines(difflines, args.exclude)
        if args.reduce:
            stripVolumePath = False if args.filename and len(volumes) > 1\
                        else True
            difflines = getReducedDifflines(
                difflines,
                stripVolumePath,
                mountpoint,
                snapshot1,
                snapshot2)

        collecteddifflines = collecteddifflines + difflines

        if args.filename:
            if volume == volumes[-1]:
                if args.filename == " ":  # report to stdout
                    logging.info("Report to stdout")
                    print("\n".join(collecteddifflines))
                else:
                    outfile = args.filename
                    writeReport(
                        collecteddifflines,
                        args.outdir,
                        outfile,
                        args.outfilesuffix,
                        args.user)
        else:  # report to separate files
            outfile = volume.replace("/", "_")+"_"+snapshot1.rsplit("@", 1)[1]
            if len(args.snapshotkeys) == 1:
                # snapshots found with same keyword
                outfile = outfile+"-"+snapshot2.rsplit(
                    args.snapshotkeys[0], 1)[1]
            # elif 0: # TODO reduce output string length if possible
            #        # for when two snapshot keys are given
            else:
                outfile = outfile+"-"+snapshot2.rsplit("@", 1)[1]
            writeReport(
                difflines,
                args.outdir,
                outfile,
                args.outfilesuffix,
                args.user)

    if errors == 0:
        logging.debug("Success")
    else:
        logging.warning("Warning: {}/{} volumes were reported. Check errors.\
".format(len(volumes)-errors, len(volumes)))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt")
