# zfsDiffReport.py

## You have...

- all your data in ZFS on your home server
- continuous snapshot routines of your volumes (e.g. with [zfs-auto-snapshot](https://github.com/zfsonlinux/zfs-auto-snapshot))
- [optional] complete trust in your data being safe from bitrot, ransomware... because you have a good mirror/send-recv backup routine for your snapshots
- ...however: *noticeable paranoia* that a file or files you deeply care about is unintentionally removed or modified by you without you noticing and you are desperately looking for a simply python script that reports exactly that information

Well...

*zfsDiffReport.py* is python a script that diffs the last two snapshots of a ZFS volume and prints report text files.

## Suggested usecase:

- set up [zfs-auto-snapshot](https://github.com/zfsonlinux/zfs-auto-snapshot) for weekly snapshots with e.g. the identifier 'zas_w-utc' (actually do it more frequently... something reasonable... four times an hour or so)
- set up a weekly cronjob and call zfsDiffReport like in the usage below (without -h)
- now, once every week, good time is a monday, when you read your morning paper in your left hand, hold the spoon for your cereal in your right, and scroll down your phone with your nose, you might as well click on the *\*_zfsDiffReport.txt* file on your server and check the short list of changes you intentionally or accidentally made during the previous week

And that's how I think you will never lose any data.

## Usage:

```
./zfsDiffReport.py ZPOOL/ZFSVOL -q -s zas_w-utc -p user:user -f /.git -f /somethingelse -h                                                                                   
usage: zfsDiffReport.py [-h] [-s SNAPSHOT] [-o OUTDIR]                                                                                                                                                             
                        [--outfilesuffix OUTFILESUFFIX] [-p PERMISSIONS]                                                                                                                                           
                        [-f FILTER] [-r] [--zfsbinary ZFSBINARY] [-v] [-q]                                                                                                                                         
                        volume                                                                                                                                                                                     
                                                                                                                                                                                                                   
zfsDiffReport.py generates a report text file from the zfs diff of a given                                                                                                                                         
volume's two last snapshots containing a given identifier.The script is                                                                                                                                            
intended to be used as companion to zfs-auto-snapshot. I use it to check my                                                                                                                                        
weekly snapshots for unintended file deletions.                                                                                                                                                                    
                                                                                                                                                                                                                   
positional arguments:                                                                                                                                                                                              
  volume                observed ZFS volume e.g.: 'ZPOOL/ZFSVOL'                                                                                                                                                   
                                                                                                                                                                                                                   
optional arguments:                                                                                                                                                                                                
  -h, --help            show this help message and exit                                                                                                                                                            
  -s SNAPSHOT, --snapshot SNAPSHOT
                        snapshot identifier e.g.: 'zas_w-utc-'
  -o OUTDIR, --outdir OUTDIR
                        Report file output directory
  --outfilesuffix OUTFILESUFFIX
                        Suffix for report text file.
                        default:'_zfsDiffReport.txt'
  -p PERMISSIONS, --permissions PERMISSIONS
                        Permissions for output file e.g.: 'user:group'
  -f FILTER, --filter FILTER
                        Multiple definitions possible. Diff lines containing a
                        filtered keyword will be omitted. e.g. '.git'
  -r, --reduce          ZFS lists a file that is deleted and (re)created
                        between snapshots with - and +. Omit those lines when
                        the files' checksums match. And modified folder path
                        lines too.
  --zfsbinary ZFSBINARY
                        Path to zfs binary. default:'zfs'
  -v, --verbose
  -q, --quiet

And that's how you report a zfs diff.
```
