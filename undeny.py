#!/usr/bin/python

'''
This script removes IP addresses that have been blocked by denyhosts.

Usage: sudo python ./undeny.py ip_address
Note: a full ip address must be provided. 

This program does the following steps:
1. Stop denyhosts.
2. Remove the specified ip_adddress from /etc/hosts.deny and other files in /var/lib/denyhosts/ 
   Reference: http://denyhosts.sourceforge.net/faq.html#3_19
   - This is done safely using a temp file followed by a copy and a remove. 
   - The copy is named with "_orig" appended.
   - If the supplied IP address is not found then the copied and original files will be identical. 
3. Start denyhosts. 

It does no harm to run this program again or on an IP address that is 
not in any of the deny hosts files. 

Notes on Renaming and Moving Files
----------------------------------

You can't use os.rename across different file systems as shown here:
    >>> import os
    >>> os.rename('/tmp/mikes','/tmp/mikes2')    # same file system, OK
    >>> os.rename('/tmp/mikes2','./mikes2')      # different file system, barfs  
    Traceback (most recent call last):
    OSError: [Errno 18] Invalid cross-device link
    >>> 

It's safer to use shutil.copy() and then a shutil.remove()

Permissions
-----------

On Centos 6.4 the permissions of the files in /var/lib/denyhosts/ are 644 (-rw-r--r--).
The temp file that we create is readable and writable only by the creating user ID 
i.e. 600 (-rw-------). Hence after the copy of the temp file overwriting the original 
denyhosts files we need to chmod the denyhosts files back to 644. 

License
-------

Copyright 2014 Mike Lake

Data Directory Cataloger is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free Software 
Foundation, either version 3 of the License, or (at your option) any later version.

Data Directory Cataloger is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
Data Directory Cataloger. If not, see http://www.gnu.org/licenses/.

Versions
--------

2013.08.19: first release by MRL
2013.08.19: added test for sudo use
2014.08.13: File opens now use 'with' and moved into function. Changed logging. Use shutil()
2014.11.06: Added more comments on what happens.
'''

import os, sys, re
import subprocess
import shutil       # required as os.rename() cannot be used. 
import tempfile
import logging
import datetime
import socket       # used to validate ip addresses


########################
# Set configuration here
########################

# Set here the full pathname to the logfile. 
# Note it's been set to be under root as root runs this program and root 
# cannot write to anyones home directory.
LOGFILE = '/root/undeny.log'

# List the denyhosts files that need to be edited.
denyhosts_files = [
    '/etc/hosts.deny',
    '/var/lib/denyhosts/hosts',
    '/var/lib/denyhosts/hosts-restricted',
    '/var/lib/denyhosts/hosts-root',
    '/var/lib/denyhosts/hosts-valid',
    '/var/lib/denyhosts/users-hosts',
    '/var/lib/denyhosts/users-invalid' ]


################
# Functions here 
################

def usage():
    print ''
    print 'Usage: sudo python %s IP_address' % sys.argv[0] 
    print '  The python invocation is required for sudo.'
    print '  The IP address must be a full dotted-quad ip address.\n' 


def check_valid_ip(address):
    '''
    Ref: http://stackoverflow.com/questions/11264005/using-a-regex-to-match-ip-addresses-in-python
    Using regex to validate IP address is a bad idea - this will pass
    999.999.999.999 as valid. Using a socket instead is much better validation
    and just as easy. 
    # TODO use except socket.error:
    '''

    try: 
        error = socket.inet_aton(address)
        return True
    except:
        return False


def denyhosts_action(action):
    '''
    Starts or stops denyhosts if the correct 'action' has been supplied. 
    '''

    if action != 'start' and action != 'stop':
        return False

    # start or stop denyhosts
    #if subprocess.call(['/bin/systemctl', action, 'denyhosts.service']) == 0:
    if subprocess.call(['service', 'denyhosts', action]) == 0:
        logging.debug('  %s denyhosts OK' % action)
        status = True
    else:
        logging.error('  Error: %s denyhosts failure' % action)
        print '  Error %s denyhosts failure' % action
        status = False

    return status


def delete_from_file(host_file, ip):
    '''
    Delete an ip address from a file. The way this is implemented is that 
    we first make a temp copy of the file and copy lines into it that don't 
    contain the unwanted ip address. After all lines are finished we rename 
    the original file (to *_orig) and then rename the temp file to what the 
    original file was named. 

    If there are errors then the original file remains the same, the temp 
    file is removed and an error logged.
    '''

    status = False

    try:   
        # The file is readable and writable only by the creating user ID.
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        with open(host_file, 'r') as fp:
            for line in fp:
                if re.search(ip, line):
                    # Found the bad ip but do nothing here because we
                    # are writing all the good IPs to a temporary file.
                    logging.debug('%s: deleted %s' % (host_file, ip) )
                else:
                    temp_file.write(line)
    except IOError:
        print '  Error: %s probably could not be opened.' % host_file 
        logging.error('  Error: %s probably could not be opened.' % host_file )
        temp_file.close()           # can run multiple times 
        os.remove(temp_file.name)   # must only run once
        status = False
    else:
        # This section will run if there were no exceptions. 
        # Note: here we must use shutil.copy() and not os.rename()
        # We also can't use shutil.move() across file systems. 
        # You have to copy then use remove. 
        temp_file.close()
        shutil.copy(host_file, host_file + '_orig') 
        shutil.copy(temp_file.name, host_file)
        os.chmod(host_file, 0644)   # this is set to be the same as in /etc/logrotate.d/denyhosts
        os.remove(temp_file.name)   # must only run once
        status = True
    finally: 
        # This section will always be run. 
        temp_file.close()

    return status



##################
# Main starts here
##################

def main():

    # Check user must run this script using sudo.
    if os.geteuid() != 0:
        usage()
        print 'Error: you have to run this script as sudo.'
        sys.exit()

    # Check user must have supplied one arg, else exit.
    if len(sys.argv) <> 2:
        usage()
        print 'Error: you need to enter an ip address.'
        sys.exit()

    # OK user supplied one arg, check format is a full IP addess.
    ip = sys.argv[1]
    if not check_valid_ip(ip):
        usage()
        print 'Error: %s is not a valid IP address.' % ip
        sys.exit()
    
    # Set the logging level. Can be DEBUG, INFO (default), or ERROR only.
    # This also checks the LOGFILE can be opened. 
    try:
        logging.basicConfig(filename=LOGFILE, level=logging.INFO, format=None)
    except IOError:
        print 'Error, can\'t find LOGFILE %s. ' % LOGFILE
        print 'Did you forget to change the value of this in this code?'
        sys.exit()

    # Log one line into the logfile.
    now = datetime.datetime.now().strftime('%Y.%m.%d %I:%M:%S %p')
    logging.info('%s  deleting %s' % (now, ip)) 
 
    # Stop denyhosts, exit if it can't be stopped.
    if not denyhosts_action('stop'):
        sys.exit()

    # Now we process the denyhosts files ....
    for host_file in denyhosts_files:
        if not delete_from_file(host_file, ip):
            # If there is any failure then don't try any more files.
            logging.error('  Error: exiting loop') 
            break

    # Start denyhosts.
    if not denyhosts_action('start'):
        print 'Error: can\t seem to start denyhosts again!'

if __name__ == '__main__':
    main()

