# NOTE: activate_this.py was removed from _venv/bin in Python 3.
# Here is the old content:
#
# """By using execfile(this_file, dict(__file__=this_file)) you will
# activate this virtualenv environment.
#
# This can be used when you must use an existing Python interpreter, not
# the virtualenv bin/python
# """
#
# try:
#     __file__
# except NameError:
#     raise AssertionError(
#         "You must run this like execfile('path/to/activate_this.py', dict(__file__='path/to/activate_this.py'))")
# import sys
# import os
#
# old_os_path = os.environ.get('PATH', '')
# os.environ['PATH'] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + old_os_path
# base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if sys.platform == 'win32':
#     site_packages = os.path.join(base, 'Lib', 'site-packages')
# else:
#     site_packages = os.path.join(base, 'lib', 'python%s' % sys.version[:3], 'site-packages')
# prev_sys_path = list(sys.path)
# import site
# site.addsitedir(site_packages)
# sys.real_prefix = sys.prefix
# sys.prefix = base
# # Move the added items to the front of the path:
# new_sys_path = []
# for item in list(sys.path):
#     if item not in prev_sys_path:
#         new_sys_path.append(item)
#         sys.path.remove(item)
# sys.path[:0] = new_sys_path

import sys
import os
import site

def wsgi_init(wsgi_path):

    prev_sys_path = list(sys.path)

    assert wsgi_path.endswith('.wsgi'), "This is not a .wsgi file: " + wsgi_path
    venv = os.path.dirname(wsgi_path) + '/_venv'
    assert os.path.exists(venv), "Missing _venv subdirectory: " + venv

    # Update PATH if necessary
    old_os_path = os.environ.get('PATH', '')
    insertion = venv + '/bin:'
    if not old_os_path.startswith(insertion):
        os.environ['PATH'] =  insertion + old_os_path

    # Update site_packages
    site_packages = os.path.join(venv, 'lib/python%s/site-packages' % sys.version[:4])
    assert os.path.exists(site_packages), "Missing site_packages subdirectory: " + site_packages
    site.addsitedir(site_packages)

    # sys.prefix
    sys.real_prefix = sys.prefix
    sys.prefix = venv

    # Move the added items to the front of sys.path
    new_sys_path = []
    for item in list(sys.path):
        if item not in prev_sys_path:
            new_sys_path.append(item)
            sys.path.remove(item)
    sys.path[:0] = new_sys_path
