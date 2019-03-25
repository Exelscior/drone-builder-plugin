FROM alpine:latest

ADD script.sh /bin/

RUN chmod +x /bin/script.sh
RUN apk -Uuv add bash docker

ENTRYPOINT [ "bash", "/bin/script.sh" ]
