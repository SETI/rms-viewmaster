Deploying with Apache / WSGI
=============================

Production deployment uses Apache with mod_wsgi. The walkthrough (required
environment variables, virtualenv via ``python-home``, and startup notes) is
in the project README under **Deploying with Apache / WSGI**.

``create_app()`` performs all startup. The WSGI entry points are two-line
factories:

* ``viewmaster.wsgi`` — Viewmaster
* ``link.wsgi`` — Link redirect service

Point ``WSGIDaemonProcess`` ``python-home`` at the virtualenv that has
``requirements.txt`` installed. That replaces the old ``wsgi_init.py`` venv
bootstrap.

A minimal vhost template:

.. literalinclude:: ../examples/apache2/viewmaster.conf
   :language: apache
