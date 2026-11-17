# Current application with the current PostgreSQL client library.
FROM adminer:6.3.0@sha256:7605e298e5a2ac74d806283362fa253a4e0a42cfd881e8fa2c155f0631899f6c
USER root
RUN apk add --no-cache libpq=18.7-r0 \
 && php --ri pdo_pgsql | grep -F 'PostgreSQL(libpq) Version => 18.7'
USER adminer
