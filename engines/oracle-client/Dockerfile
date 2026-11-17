# Independent current query/export clients, leaving the Free server's bootstrap
# binaries intact. Building this image does not start Oracle or accept its DB licence.
ARG ORACLE_IMAGE=gvenzl/oracle-free:23@sha256:7ed34d0ade89c91a553c9cbe9d42457c758fa29a762aaaa3137541ff30a2d1cb
FROM debian:13.7-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 AS clients
RUN apt-get update -qq && apt-get install -y --no-install-recommends ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
RUN curl -fL --retry 3 -o /basic.zip https://download.oracle.com/otn_software/linux/instantclient/2326400/instantclient-basic-linux.x64-23.26.4.0.0.zip \
 && echo 'cab59aa3b411b3b50898e456fa9aabfe48d67e25cbc1bb23303800390ce7de26  /basic.zip' | sha256sum -c - \
 && curl -fL --retry 3 -o /sqlplus.zip https://download.oracle.com/otn_software/linux/instantclient/2326400/instantclient-sqlplus-linux.x64-23.26.4.0.0.zip \
 && echo '3cd43219cbaad59bb75cee18e7af074ada707446f13397b6f93ec7e4ca870490  /sqlplus.zip' | sha256sum -c - \
 && curl -fL --retry 3 -o /tools.zip https://download.oracle.com/otn_software/linux/instantclient/2326400/instantclient-tools-linux.x64-23.26.4.0.0.zip \
 && echo '95e60dedcaf64a4ebc4dded73f5614c494a8c17fa272cd3c0485e0d13e825000  /tools.zip' | sha256sum -c - \
 && mkdir /clients \
 && unzip -oq /basic.zip -d /clients && unzip -oq /sqlplus.zip -d /clients && unzip -oq /tools.zip -d /clients \
 && set -- /clients/instantclient_* && test "$#" -eq 1 && mv "$1" /instantclient

FROM ${ORACLE_IMAGE}
USER root
COPY --from=clients /instantclient /opt/megasamples/instantclient
COPY client-wrapper.sh /usr/local/bin/megasamples-oracle-client
RUN chmod 755 /usr/local/bin/megasamples-oracle-client \
 && ln -s megasamples-oracle-client /usr/local/bin/megasamples-sqlplus \
 && ln -s megasamples-oracle-client /usr/local/bin/megasamples-sqlldr
USER oracle
