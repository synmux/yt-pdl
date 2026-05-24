FROM python:3.14.0-alpine3.21
HEALTHCHECK CMD "yt-pdl --version"
RUN adduser -h /app -D ytpdl
USER ytpdl
COPY . /app
ENV PATH="/app/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
RUN /usr/local/bin/pip install --user --no-cache-dir pipx && \
  /app/.local/bin/pipx install /app
ENTRYPOINT ["yt-pdl"]
