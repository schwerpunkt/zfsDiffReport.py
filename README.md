# zfsDiffReport.py

## You have...

- all your data in ZFS on your home server
- continuous snapshot routines of your volumes (e.g. with [zfs-auto-snapshot](https://github.com/zfsonlinux/zfs-auto-snapshot))
- [optional] complete trust in your data being safe from bitrot, ransomware... because you have a good mirror/send-recv backup routine for your snapshots
- ...however: *noticeable paranoia* that a file or files you deeply care about are unintentionally removed or modified by you without you noticing and you are longing for a simple python script that reports exactly that information

Well...

*zfsDiffReport.py* is a python script that diffs the last two snapshots of a ZFS volume and prints report text files.

## Suggested usecase:

- set up [zfs-auto-snapshot](https://github.com/zfsonlinux/zfs-auto-snapshot) for weekly snapshots with e.g. the identifier 'zas_w-utc' (actually do it more frequently... something reasonable... four times an hour or so)
- set up a weekly cronjob and call zfsDiffReport like in the usage below (without -h)
- now, once every week, good time is a monday, when you read your morning paper in your left hand, hold the spoon for your cereal in your right, and scroll down your phone with your nose, you might as well click on the *\*_zfsDiffReport.txt* file on your server and check the short list of changes you intentionally or accidentally made during the previous week

And that's how I think you will never lose any data.

## Usage:

```
./zfsDiffReport.py ZPOOL/ZFSVOL -q -s zas_w-utc -u user -e /.git -e somethingelse -h                                                                                   
usage: zfsDiffReport.py [-h] [-s SNAPSHOTKEYWORD] [-o OUTDIR] [-f [FILENAME]]
                        [--outfilesuffix OUTFILESUFFIX] [-u USER] [-e EXCLUDE]
                        [-r] [--zfsbinary ZFSBINARY] [--debug] [-q]
                        volume [volume ...]

zfsDiffReport.py generates a report text file from the zfs diff of a given
volume's two last snapshots containing a given identifier.The script is
intended to be used as companion to zfs-auto-snapshot. I use it to check my
weekly snapshots for unintended file deletions.

positional arguments:
  volume                observed ZFS volume(s) e.g.: 'ZPOOL/ZFSVOL'

optional arguments:
  -h, --help            show this help message and exit
  -s SNAPSHOTKEYWORD, --snapshotkeyword SNAPSHOTKEYWORD
                        snapshot keyword e.g.: 'zas_w-utc-'
  -o OUTDIR, --outdir OUTDIR
                        report file output directory
  -f [FILENAME], --filename [FILENAME]
                        optional filename. If set all volume diffs are written
                        to it. If empty reports are written to stdout.
  --outfilesuffix OUTFILESUFFIX
                        suffix for report text file. default:
                        '_zfsDiffReport.txt'
  -u USER, --user USER  user for output file e.g.: 'user'
  -e EXCLUDE, --exclude EXCLUDE
                        multiple definitions possible. Diff lines containing
                        an exclude keyword will be omitted. e.g. '.git'
  -r, --reduce          ZFS lists a file that is deleted and (re)created
                        between snapshots with - and +. Omit those lines when
                        the files' checksums match. And modified folder path
                        lines too.
  --zfsbinary ZFSBINARY
                        path to zfs binary. default: 'zfs'
  --debug
  -q, --quiet

And that's how you report a zfs diff.
```
