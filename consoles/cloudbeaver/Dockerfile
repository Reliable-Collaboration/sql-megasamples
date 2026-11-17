# Current application plus the configured MySQL and SQLite drivers. The original
# library filenames are DBeaver's plugin lookup paths, not the replacement versions.
FROM debian:13.7-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 AS drivers
RUN apt-get update -qq && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
RUN curl -fL --retry 3 -o /mysql.jar https://repo.maven.apache.org/maven2/com/mysql/mysql-connector-j/26.10.0/mysql-connector-j-26.10.0.jar \
 && echo 'cef70caf532833c9ab8f41f74773ce22c08bf503fad215c9c2ee1e9db87e759e  /mysql.jar' | sha256sum -c - \
 && curl -fL --retry 3 -o /sqlite.jar https://repo.maven.apache.org/maven2/org/xerial/sqlite-jdbc/3.54.1.0/sqlite-jdbc-3.54.1.0.jar \
 && echo 'f8dce420a6016278497f4f0560f65602b9db858de141b541cf91a4644ebe4639  /sqlite.jar' | sha256sum -c -
FROM dbeaver/cloudbeaver:26.2.5@sha256:5de1c6aa18da9e369966f88a1b25fe017b70ce3fdac7d879616aa931e44b013f
COPY --from=drivers /mysql.jar /opt/cloudbeaver/drivers/mysql/mysql8/mysql-connector-j-8.2.0.jar
COPY --from=drivers /sqlite.jar /opt/cloudbeaver/drivers/sqlite/xerial/sqlite-jdbc-3.48.0.0.jar
