FROM python:3.7.2-alpine3.9

RUN apk -Uuv add docker

COPY script.py /bin/
RUN chmod +x /bin/script.py

ENTRYPOINT [ "/bin/script.py" ]
