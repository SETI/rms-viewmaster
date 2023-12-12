from wsgi_init import wsgi_init

wsgi_init(__file__)

from viewmaster import app as application

