# Preserve Adminer and its entrypoint while rebuilding every database extension for PHP 8.5.
FROM adminer:6.3.0@sha256:7605e298e5a2ac74d806283362fa253a4e0a42cfd881e8fa2c155f0631899f6c AS app
FROM php:8.5.12-cli-alpine3.24@sha256:1ff5b45922ab30f418447c6089dbe2eba5f01e0b2742863d0327ac349305d70f AS extensions
RUN apk add --no-cache $PHPIZE_DEPS freetds-dev unixodbc-dev postgresql18-dev=18.7-r0 \
 && docker-php-ext-configure pdo_dblib --with-pdo-dblib=/usr \
 && docker-php-ext-configure pdo_odbc --with-pdo-odbc=unixODBC,/usr \
 && docker-php-ext-install -j4 mysqli pdo_dblib pdo_odbc pdo_pgsql
FROM php:8.5.12-cli-alpine3.24@sha256:1ff5b45922ab30f418447c6089dbe2eba5f01e0b2742863d0327ac349305d70f
RUN apk add --no-cache freetds unixodbc libpq=18.7-r0 \
 && addgroup -S -g 1000 adminer && adduser -S -D -u 1000 -G adminer -h /var/www/html adminer
COPY --from=extensions /usr/local/lib/php/extensions/ /usr/local/lib/php/extensions/
COPY --from=extensions /usr/local/etc/php/conf.d/ /usr/local/etc/php/conf.d/
COPY --from=app /usr/local/etc/php/conf.d/0-upload_large_dumps.ini /usr/local/etc/php/conf.d/0-upload_large_dumps.ini
COPY --from=app /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --from=app --chown=adminer:adminer /var/www/html/ /var/www/html/
ENV ADMINER_VERSION="6.3.0"
ENV ADMINER_DOWNLOAD_SHA256="641e1a31e8cc333a309e202ef9446e1fd38c2069ed5f9ee509b80d70089d0503"
ENV ADMINER_SRC_DOWNLOAD_SHA256="651353bc14d125b548c429cc3ffaa30b97c8b0f86b1b1692138a35a2047fba3a"
RUN php -m >/tmp/php-modules 2>/tmp/php-startup-errors && test ! -s /tmp/php-startup-errors \
 && php -r 'if (PHP_VERSION !== "8.5.12") exit(1); foreach (["mysqli","pdo_pgsql","pdo_dblib","pdo_odbc"] as $e) { if (!extension_loaded($e)) exit(1); } echo PHP_VERSION," ",mysqli_get_client_info(),"\n";' \
 && php --ri pdo_pgsql | grep -F 'PostgreSQL(libpq) Version => 18.7'
WORKDIR /var/www/html
USER adminer
ENTRYPOINT ["entrypoint.sh", "docker-php-entrypoint"]
CMD ["php", "-S", "[::]:8080", "-t", "/var/www/html"]
