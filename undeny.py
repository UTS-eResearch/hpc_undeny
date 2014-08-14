#!/usr/bin/python
#
# Usage: sudo python ./undeny.py ip_address
# Note: a full ip address must be provided. 
#
# This program does the following steps:
# 1. stop denyhosts 
# 2. remove the specified ip_adddress from 
#    /etc/hosts.deny and the 5 other files in /var/lib/denyhosts/ 
# 3. start denyhosts 
#
# From: http://serverfault.com/questions/189932/how-to-delete-ip-address-from-denyhosts
# Substantially modified by MRL for Centos.
#
# Versions:
# 2013.08.19: first release by MRL
# 2013.08.19: added test for sudo use
# 2014.08.13: File opens now use 'with' and moved into function. Changed logging.
#             Use shutil()

import os, sys, re
import subprocess
import shutil       # required as os.move() cannot be used. 
import tempfile
import logging
import datetime
import socket       # used to validate ip addresses

########################
# Set configuration here
########################

# Set here the full pathname name of the logfile. 
LOGFILE = '/shared/homes/mlake/undeny.log'

# Set the logging level. Can be DEBUG, INFO (default), or ERROR only.
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format=None)

# List the denyhosts files that need to be edited.
denyhosts_files = [
    '/etc/hosts.deny',
    '/var/lib/denyhosts/hosts',
    '/var/lib/denyhosts/hosts-restricted',
    '/var/lib/denyhosts/hosts-root',
    '/var/lib/denyhosts/hosts-valid',
    '/var/lib/denyhosts/users-hosts',
    '/var/lib/denyhosts/users-invalid' ]


def usage():
    print ''
    print 'Usage: sudo %s IP_address' % sys.argv[0] 
    print '  The IP address must be a full dotted-quad ip address.\n' 


def check_valid_ip(address):
    '''
    Ref: http://stackoverflow.com/questions/11264005/using-a-regex-to-match-ip-addresses-in-python
    Using regex to validate IP address is a bad idea - this will pass
    999.999.999.999 as valid. Using a socket instead is much better validation
    and just as easy. 
    #except socket.error:
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
        # Note: here we must use shutil.copy() and not os.move()
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
    if os.geteuid() != 0 and not TEST:
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

