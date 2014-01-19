decss-sync
==========

A tornado.py web app for syncing Decss presentations.

## Usage

This is intended to be used as an asynchronous WebSocket server for [Decss](https://github.com/dryan/decss).

For help with running tornado under nginx, see (http://stackoverflow.com/questions/14749655/setting-up-a-tornado-web-service-in-production-with-nginx-reverse-proxy)[http://stackoverflow.com/questions/14749655/setting-up-a-tornado-web-service-in-production-with-nginx-reverse-proxy].

To setup which host domains are allowed to control presentations, set an environment variable of DECSS_SYNC_ALLOWED_MASTERS to a comma-separated list of domain names.