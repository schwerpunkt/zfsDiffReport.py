#!/usr/bin/env python3

import logging
import argparse
import subprocess
import os
from pwd import getpwnam
import hashlib
from pathlib import Path

DESCRIPTION = "\
zfsDiffReport.py generates a report text file from the zfs diff of a given \
volume's two last snapshots containing a given identifier.\
\
The script is intended to be used as companion to zfs-auto-snapshot. \
I use it to check my weekly snapshots for unintended file deletions.\
"

EPILOG = "\
And that's how you report a zfs diff.\
"

def getArgs():
  parser = argparse.ArgumentParser(description=DESCRIPTION,epilog=EPILOG)
  parser.add_argument("volume",nargs="+",
    help="observed ZFS volume(s) e.g.: 'ZPOOL/ZFSVOL'")
  parser.add_argument("-s","--snapshotkeyword",default="",
    help="snapshot keyword e.g.: 'zas_w-utc-'")
  parser.add_argument("-o","--outdir",default=".",
    help="report file output directory")
  parser.add_argument("-f","--filename",nargs="?",const=" ",
    help="optional filename. If set all volume diffs are written to it. If empty reports are written to stdout.")
  parser.add_argument("--outfilesuffix",default="_zfsDiffReport.txt",
    help="suffix for report text file. default: '_zfsDiffReport.txt'")
  parser.add_argument("-u","--user",
    help="user for output file e.g.: 'user'")
  parser.add_argument("-e","--exclude",action="append",
    help="multiple definitions possible. Diff lines containing an exclude keyword will be omitted. e.g. '.git'")
  parser.add_argument("-r","--reduce",action="store_true",
    help="ZFS lists a file that is deleted and (re)created between snapshots with - and +. Omit those lines when the files' checksums match. And modified folder path lines too.")
  parser.add_argument("--zfsbinary",default="zfs",
    help="path to zfs binary. default: 'zfs'")
  parser.add_argument("--debug",action="store_true")
  parser.add_argument("-q","--quiet",action="store_true")
  return parser.parse_args()


def handleLogging(args):
  if args.debug:
    logging.basicConfig(level=logging.DEBUG,format="%(levelname)-8s %(asctime)-15s %(message)s")
  elif args.quiet:
    logging.basicConfig(level=logging.CRITICAL,format="%(levelname)-8s %(message)s")
  else:
    logging.basicConfig(level=logging.INFO,format="%(message)s")


def getSnapshots(volume,snapshotkeyword):
  logging.info("Get snapshot list for {}".format(volume))
  process       = subprocess.Popen(["zfs list -t snapshot -o name -s creation -r {}".format(volume)],shell=True,stdout=subprocess.PIPE)
  stdout,stderr = process.communicate()
  zfssnapshots  = stdout.decode("utf-8").splitlines()

  if snapshotkeyword != "":
    logging.debug("Filter snapshots for {}".format(snapshotkeyword))
    zfssnapshots = list(filter(lambda x:snapshotkeyword in x, zfssnapshots))

  enoughSnapshots = True if len(zfssnapshots) > 1  else False
  snapshot1 = zfssnapshots[-2] if enoughSnapshots else ""
  snapshot2 = zfssnapshots[-1] if enoughSnapshots else ""
  if not enoughSnapshots:
    logging.critical("ERROR: Not enough snapshots in volume {}{}".format(volume," for snapshot identifier {}".format(snapshotkeyword) if snapshotkeyword else ""))

  return enoughSnapshots,snapshot1,snapshot2


def getSortedDiffLines(snapshot1,snapshot2):
  logging.info("Create zfs diff of snapshots {} and {}".format(snapshot1,snapshot2))
  process       = subprocess.Popen(["zfs diff {} {}".format(snapshot1,snapshot2)],shell=True,stdout=subprocess.PIPE)
  stdout,stderr = process.communicate()
  difflines     = stdout.decode("utf-8")

  # TODO change this to proper decoding! https://unix.stackexchange.com/questions/216312/convert-an-ascii-file-with-octal-escapes-for-utf-8-codes-to-utf-8
  difflines = difflines.replace("\\0040"," ")
  difflines = difflines.replace("\\0303\\0244","ä")
  difflines = difflines.replace("\\0303\\0204","Ä")
  difflines = difflines.replace("\\0303\\0266","ö")
  difflines = difflines.replace("\\0303\\0226","Ö")
  difflines = difflines.replace("\\0303\\0274","ü")
  difflines = difflines.replace("\\0303\\0234","Ü")
  
  difflines = difflines.splitlines()

  # sorting difflines by second column
  return sorted(difflines,key=lambda x: x.split()[1])


def getFilteredDifflines(difflines,excludes):
  if excludes:
      logging.info("Exclude lines containing '{}'".format(" or ".join(excludes)))
      difflines = list(filter(lambda x:not any(f in x for f in excludes),difflines))
  return difflines


def getHash(file):
  if Path(file).is_dir():
    return ""
  if not Path(file).is_file():
    return ""
  # code from : https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file?answertab=votes#tab-top
  hash_alg = hashlib.sha1()
  with open(file,"rb") as f:
    for chunk in iter(lambda: f.read(4096), b""):
      hash_alg.update(chunk)
  return hash_alg.hexdigest()


def getReducedDifflines(difflines,stripVolumePath,mountpoint,snapshot1,snapshot2):
  zfsstructure = "/.zfs/snapshot/"
  snapshot1 = mountpoint+zfsstructure+snapshot1.split("@")[1]
  snapshot2 = mountpoint+zfsstructure+snapshot2.split("@")[1]
  logging.debug("Reduce lines after hashing some files from {} and {}. stripVolumePath {}".format(snapshot1,snapshot2,stripVolumePath))

  reduceddifflines = []
  mreduced = False
  for index,line in enumerate(difflines):
    # TODO write separate reduced line file maybe

    if mreduced:
      mreduced = False
      logging.debug("Reducing line {}".format(line))
      continue

    if line.startswith("M") and len(line) > 3:
      mfile = line.split("{}".format(mountpoint))[1]
      mhash1 = getHash(snapshot1+mfile)
      mhash2 = getHash(snapshot2+mfile)
      line = "{} {} {}".format(line,mhash1,mhash2)
      if mhash1 == mhash2:
        logging.debug("Reducing line {}".format(line))
        continue

    elif line.startswith("-") \
         and index+1 < len(difflines) \
         and difflines[index+1].startswith("+"):
      mfile = line.split("{}".format(mountpoint))[1]
      pfile = difflines[index+1].split("{}".format(mountpoint))[1]
      if mfile == pfile:
        mhash = getHash(snapshot1+mfile)
        phash = getHash(snapshot1+pfile)
        line  = "{} {}".format(line,mhash)
        difflines[index+1] = "{} {}".format(difflines[index+1],phash)
        if mhash == phash:
          logging.debug("Reducing line {}".format(line))
          mreduced = True
          continue

    if stripVolumePath:
      line = line.replace(mountpoint,"",1)

    line = " ".join(line.split())

    reduceddifflines.append(line)

  return reduceddifflines


def writeReport(difflines,outdir,outfile,outfilesuffix,user):
  outpath = outdir+"/"+outfile+outfilesuffix
  logging.info("Write to {}".format(outpath))
  file = open(outpath,"w")
  file.write("\n".join(difflines))
  file.close()

  if user:
    logging.debug("Setting user for user {}".format(user))
    os.chown(outpath,getpwnam(user).pw_uid,getpwnam(user).pw_gid)


def main():
  args = getArgs()
  handleLogging(args)

  # args check
  try:
    if args.user :
      getpwnam(args.user)
  except KeyError:
    logging.critical("ERROR: Given user does not exist")
    return

  if os.geteuid() != 0:
    logging.warning("Warning: Root privileges are expected.")

  if not Path(args.outdir).is_dir():
    logging.critical("ERROR: Output directory does not exist.")
    return

  # remove volume duplicates
  volumes = list(set(args.volume))

  collecteddifflines = []
  errors = 0
  for volume in volumes:
    mountpoint = "/{}".format(volume) # TODO get actual mountpoint
    getSnapshotsSuccess,snapshot1,snapshot2 = getSnapshots(volume,args.snapshotkeyword)
    if not getSnapshotsSuccess:
      errors += 1
      continue
  
    difflines = getSortedDiffLines(snapshot1,snapshot2)
    difflines = getFilteredDifflines(difflines,args.exclude)
    if args.reduce:
      stripVolumePath = False if args.filename and len(volumes) > 1 else True
      difflines = getReducedDifflines(difflines,stripVolumePath,mountpoint,snapshot1,snapshot2)

    collecteddifflines = collecteddifflines + difflines
  
    if args.filename:
      if volume == volumes[-1]:
        if args.filename == " ": # report to stdout
          logging.info("Report to stdout")
          print("\n".join(collecteddifflines))
        else:
          outfile = args.filename
          writeReport(collecteddifflines,args.outdir,outfile,args.outfilesuffix,args.user)
    else: # report to separate files
      outfile = volume.replace("/","_")+"_"+snapshot1.rsplit("@",1)[1]
      if args.snapshotkeyword:
        outfile = outfile+"-"+snapshot2.rsplit(args.snapshotkeyword,1)[1]
      else:
        outfile = outfile+"-"+snapshot2.rsplit("@",1)[1]
      writeReport(difflines,args.outdir,outfile,args.outfilesuffix,args.user)

  if errors == 0:
    logging.debug("Success")
  else:
    logging.warning("Warning: {}/{} volumes were reported. Check errors.".format(len(volumes)-errors,len(volumes)))

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    logging.info("Received KeyboardInterrupt")