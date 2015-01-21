#!/bin/bash

# This restores the original test files to the test/ directory.

# Create the test dir if it does not exist.
mkdir -p test

# Cleanout any "_orig" files created by the undeny.py script.
# The 2>/dev/null is to hide errors when there are no _orig files under test/
rm -f test/etc/hosts.deny_orig
find test/var/lib/denyhosts/ -name "*_orig" 2>/dev/null | xargs rm -f 

# Remove temp files created by undeny.py 
# Note: this will remove other temp files owned by you. 
find /tmp -maxdepth 1 -name tmp* -user ${USER} -type f | xargs rm -f 

# Restore the original test files.
tar xf test_restore.tar

