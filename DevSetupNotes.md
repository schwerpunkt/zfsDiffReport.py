# Development Setup Notes

Install [zfs on debian](https://github.com/zfsonlinux/zfs/wiki/Debian)

## Creating zpools in a file

```sh
truncate --size 1G disk1.img
zpool create zfsTestPool $PWD/disk1.img
zfs create zfsTestPool/VolOne
zfs create zfsTestPool/VolTwo
```
## Test snapshots with [zfs-auto-snapshot](https://packages.debian.org/sid/utils/zfs-auto-snapshot)

```sh
zfs-auto-snapshot -p zas -l f-utc -k 4 -r zfsTestPool
```
