# Preserve the released application/configuration on the current PHP 8 branch.
FROM phpmyadmin:5.2.3@sha256:e4b3eb5305cd42d21512bb55def2bab52625d56df927ad4ee1864a9354c84d40 AS app
FROM php:8.5.12-apache-trixie@sha256:08af36df144462d84c7f16190557eec06cb9f656882685610b712a15eec54d46 AS extensions
RUN apt-get update -qq && apt-get install -y --no-install-recommends $PHPIZE_DEPS libbz2-dev libpng-dev libfreetype6-dev libjpeg62-turbo-dev libwebp-dev libzip-dev \
 && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
 && docker-php-ext-install -j4 bcmath bz2 gd mysqli zip
RUN curl -fL --retry 3 -o /tmp/uploadprogress.tgz https://pecl.php.net/get/uploadprogress-2.0.2.tgz \
 && echo '2c63ce727340121044365f0fd83babd60dfa785fa5979fae2520b25dad814226  /tmp/uploadprogress.tgz' | sha256sum -c - \
 && tar -xzf /tmp/uploadprogress.tgz -C /tmp && cd /tmp/uploadprogress-2.0.2 \
 && phpize && ./configure && make -j4 && make install \
 && docker-php-ext-enable uploadprogress \
 && mkdir -p /usr/local/share/doc/uploadprogress \
 && cp /tmp/uploadprogress.tgz /usr/local/share/doc/uploadprogress/source-2.0.2.tgz
FROM php:8.5.12-apache-trixie@sha256:08af36df144462d84c7f16190557eec06cb9f656882685610b712a15eec54d46
RUN apt-get update -qq && apt-get install -y --no-install-recommends libbz2-1.0 libpng16-16t64 libfreetype6 libjpeg62-turbo libwebp7 libzip5 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=app /etc/apache2/ /etc/apache2/
COPY --from=app /etc/phpmyadmin/ /etc/phpmyadmin/
COPY --from=app /sessions/ /sessions/
COPY --from=app /var/www/html/ /var/www/html/
COPY --from=app /docker-entrypoint.sh /docker-entrypoint.sh
COPY --from=app /usr/local/etc/php/conf.d/ /usr/local/etc/php/conf.d/
# Replace every extension loader with this ABI's rebuilt modules; retain app INI settings.
RUN rm -f /usr/local/etc/php/conf.d/docker-php-ext-*.ini
COPY --from=extensions /usr/local/lib/php/extensions/ /usr/local/lib/php/extensions/
COPY --from=extensions /usr/local/etc/php/conf.d/ /usr/local/etc/php/conf.d/
COPY --from=extensions /usr/local/share/doc/uploadprogress/ /usr/local/share/doc/uploadprogress/
ENV UPLOAD_PROGRESS_EXT_URL="https://pecl.php.net/get/uploadprogress-2.0.2.tgz"
ENV UPLOAD_PROGRESS_SHA256="2c63ce727340121044365f0fd83babd60dfa785fa5979fae2520b25dad814226"
ENV PMA_SSL_DIR="/etc/phpmyadmin/ssl"
ENV MAX_EXECUTION_TIME="600"
ENV MEMORY_LIMIT="512M"
ENV UPLOAD_LIMIT="2048K"
ENV TZ="UTC"
ENV SESSION_SAVE_PATH="/sessions"
ENV VERSION="5.2.3"
ENV SHA256="57881348297c4412f86c410547cf76b4d8a236574dd2c6b7d6a2beebe7fc44e3"
ENV URL="https://files.phpmyadmin.net/phpMyAdmin/5.2.3/phpMyAdmin-5.2.3-all-languages.tar.xz"
RUN php -m >/tmp/php-modules 2>/tmp/php-startup-errors && test ! -s /tmp/php-startup-errors \
 && php -r 'if (PHP_VERSION !== "8.5.12") exit(1); foreach (["bcmath","bz2","gd","mysqli","zip","uploadprogress"] as $e) { if (!extension_loaded($e)) exit(1); } if (phpversion("uploadprogress") !== "2.0.2") exit(1); echo PHP_VERSION," ",mysqli_get_client_info(),"\n";'
WORKDIR /var/www/html
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["apache2-foreground"]
