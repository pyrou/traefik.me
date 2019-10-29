```
           888                              .d888 d8b 888
           888                             d88P"  Y8P 888
           888                             888        888
           888888 https://8888b.   .d88b.  888888 888 888  888     88888b.d88b.   .d88b.
           888    888P"      "88b d8P  Y8b 888    888 888 .88P     888 "888 "88b d8P  Y8b
           888    888    .d888888 88888888 888    888 888888K      888  888  888 88888888
           Y88b.  888    888  888 Y8b.     888    888 888 "88b d8b 888  888  888 Y8b.
            "Y888 888    "Y888888  "Y8888  888    888 888  888 Y8P 888  888  888  "Y8888
```

## What is traefik.me?
Just like nip.io or xip.io, [traefik.me](https://traefik.me) is a magic domain name that provides
wildcard DNS for any IP address. Say your LAN IP address is 10.0.0.1.
Using traefik.me,

```
                 10.0.0.1.traefik.me   resolves to   10.0.0.1
             www.10.0.0.1.traefik.me   resolves to   10.0.0.1
          mysite.10.0.0.1.traefik.me   resolves to   10.0.0.1
   foo.bar.208.132.27.194.traefik.me   resolves to   208.132.27.194
```
...and so on. You can use these domains to access virtual hosts on your
development web server from devices on your local network, like iPads, iPhones,
and other computers. No configuration required!

Alternatively, traefik works with dashes, and provide a default resolving to
127.0.0.1, pretty handy in a local configuration:

```
                 10-0-0-1.traefik.me   resolves to   10.0.0.1
             www-10-0-0-1.traefik.me   resolves to   10.0.0.1
                   mysite.traefik.me   resolves to   127.0.0.1
                  foo.bar.traefik.me   resolves to   127.0.0.1
```

## How does it work?

traefik.me runs a custom DNS server on the public Internet.
When your computer looks up a traefik.me domain, the traefik.me DNS server
extracts the IP address from the domain and sends it back in the response.

## HTTPS support!

Thanks to Let's encrypt, a wildcard certificate is available for *.traefik.me.
Just grab the files on traefik.me. As wildcard certificates are only valid for one level depth subdomains, use the
dashed-form subdomain instead of dots. Certificates are regenerated every 60 days.

## Ok but why "traefik"?
The name comes from [traefik.io](http://traefik.io), that is an open-source reverse proxy and load
balancer. Used in conjonction with docker, it becomes very handy for local web
development. Here is a typical `docker-compose.yml` file you might produce:
```yml
version: '3'
services:
  traefik:
    restart: unless-stopped
    image: traefik:v2.0.2
    command: --providers.docker=true
    ports:
      - "80:80"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
  app1:
    image: containous/whoami
    labels:
      - "traefik.http.routers.app1.rule=Host(`app1.traefik.me`)"
  app2:
    image: containous/whoami
    labels:
      - "traefik.http.routers.app2.rule=Host(`app2.traefik.me`)"
```

Launch it with docker-compose up. Open your browser, and visit app1.traefik.me
or app2.traefik.me. It just works as expected out of the box, without additional
configuration or /etc/hosts tuning.

To reach the container from another device on your local network, use the
following docker label :

    - "traefik.http.routers.app1.rule=HostRegexp(`app1.{ip:.*}.traefik.me`)"

Say your LAN IP address is 10.0.0.1, visiting http://app1.10.0.0.1.traefik.me
from any device on your local network will reach your app1 docker container.

## Copyright
Kudos to [xip.io](https://xip.io) for the inspiration of the website, [nip.io](https://github.com/exentriquesolutions/nip.io) for the dns
server.
