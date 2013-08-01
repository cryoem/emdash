#!/usr/bin/env python
import sys
import emdash.console

def print_help():
    print """%s <action>

Actions available: upload, download
For detailed help: %s <action> --help
    """%(sys.argv[0],sys.argv[0])
    
    
def main():
    if len(sys.argv) < 2:
        print_help()
        return
    action = sys.argv[1]
    sys.argv.pop(1)
    if action == 'upload':
        emdash.console.upload()    
    elif action == 'download':
        emdash.console.download()


if __name__ == "__main__":
    main()


