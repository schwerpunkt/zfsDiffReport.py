#!/usr/bin/env python3

import logging
import argparse
import subprocess
import os
from pwd import getpwnam

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
  
  parser.add_argument("volume",help="observed ZFS volume e.g.: 'ZPOOL/ZFSVOL'")
  parser.add_argument("-s","--snapshot",default="",dest="snapshot",help="snapshot identifier e.g.: 'zas_w-utc-'")
  parser.add_argument("-o","--outdir",default=".",help="Report file output directory")
  parser.add_argument("-f","--filename",nargs="?",const=" ",help="Optional filename. If set all volume diffs are written to it. If empty reports are written to stdout.")
  parser.add_argument("--outfilesuffix",default="_zfsDiffReport.txt",help="Suffix for report text file. default: '_zfsDiffReport.txt'")
  parser.add_argument("-p","--permissions",default="",help="Permissions for output file e.g.: 'user'")
  parser.add_argument("-e","--exclude",action="append",help="Multiple definitions possible. Diff lines containing an exclude keyword will be omitted. e.g. '.git'")
  parser.add_argument("-r","--reduce",action="store_true",help="ZFS lists a file that is deleted and (re)created between snapshots with - and +. Omit those lines when the files' checksums match. And modified folder path lines too.")
  parser.add_argument("--zfsbinary",default="zfs",help="Path to zfs binary. default: 'zfs'")
  parser.add_argument("-v","--verbose",action="store_true",help="")
  parser.add_argument("-q","--quiet",action="store_true",help="")
  
  return parser.parse_args()

def handleLogging(args):
  if args.verbose:
    logging.basicConfig(level=logging.DEBUG,format="%(levelname)-8s %(asctime)-15s %(message)s")
  elif args.quiet:
    logging.basicConfig(level=logging.CRITICAL,format="%(levelname)-8s %(message)s")
  else:
    logging.basicConfig(level=logging.INFO,format="%(message)s")


def getSnapshots(volume,snapshotidentifier):
  logging.info("Get snapshot list for {}".format(volume))
  process       = subprocess.Popen(["zfs list -t snapshot -o name -s creation -r {}".format(volume)],shell=True,stdout=subprocess.PIPE)
  stdout,stderr = process.communicate()
  zfssnapshots  = stdout.decode("ascii").splitlines()

  if snapshotidentifier != "":
    logging.debug("Filtering snapshots for {}".format(snapshotidentifier))
    zfssnapshots = list(filter(lambda x:snapshotidentifier in x, zfssnapshots))
  return zfssnapshots[-2],zfssnapshots[-1]


def getSortedDiffLines(snapshot1,snapshot2):
  logging.info("Creating zfs diff of snapshots {} and {}".format(snapshot1,snapshot2))
  process       = subprocess.Popen(["zfs diff {} {}".format(snapshot1,snapshot2)],shell=True,stdout=subprocess.PIPE)
  stdout,stderr = process.communicate()
  difflines     = stdout.decode("ascii").splitlines()

  # sorting difflines by second column
  # TODO split this now into a multi list, so you don't have to split it later. also multi sort it
  return sorted(difflines,key=lambda x: x.split()[1])


def writeReport(difflines,outdir,outfile,outfilesuffix,permissions):
  outpath = outdir+"/"+outfile+outfilesuffix
  logging.info("Writing to {}".format(outpath))
  f = open(outpath,"w")
  for index,line in enumerate(difflines):
    f.write("{}\n".format(line))
  f.close()

  if permissions != "":
    logging.debug("Setting permissions for user {}".format(permissions))
    os.chown(outpath,getpwnam(permissions).pw_uid,getpwnam(permissions).pw_gid)

def main():
  args = getArgs()

  handleLogging(args)

  logging.debug("TODO am I root (zfs/permissionschange)")
  logging.debug("TODO does ZFS volume {} exist?".format(args.volume))
  logging.debug("TODO does directory {}/ exist?".format(args.outdir))
  logging.debug("TODO are there enough zfs snapshots?")
  logging.debug("TODO does user {} exist?".format(args.permissions))
  # TODO check this for all volumes before start

  snapshot1,snapshot2 = getSnapshots(args.volume,args.snapshot)

  difflines = getSortedDiffLines(snapshot1,snapshot2)

  if args.exclude:
    for f in args.exclude:
      logging.info("Exclude lines containing '{}'".format(f))
    difflines = list(filter(lambda x:not any(f in x for f in args.exclude),difflines))

  # TODO reduce duplicates after checksum comparison

  # TODO start a single out instance if writing to stdout or to given filename
  if args.filename:
    if args.filename == " ":
      logging.info("Reporting to stdout")
      print("\n".join(difflines))
    else: # TODO if volume == last
      outfile = args.filename
      writeReport(difflines,args.outdir,outfile,args.outfilesuffix,args.permissions)
  else:
    outfile = args.volume.replace("/","_")+"_"+snapshot1.rsplit("@",1)[1]+"-"+snapshot2.rsplit(args.snapshot,1)[1]
    writeReport(difflines,args.outdir,outfile,args.outfilesuffix,args.permissions)

  logging.debug("Success")

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    logging.info("Received KeyboardInterrupt")