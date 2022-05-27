FROM iwdcibot/iwd-ubuntu-build:latest

COPY *.sh /
COPY *.py /
COPY *.ini /

ENTRYPOINT [ "/entrypoint.sh" ]
