FROM alpine:3.18.4 as build
WORKDIR /opt/AlarmPI

RUN apk update && apk add jq python3 py3-pip gcc libc-dev python3-dev

COPY . /opt/AlarmPI
WORKDIR /opt/AlarmPI
RUN pip3 install -r requirements.txt
RUN cp config/settings_template.json config/settings.json
RUN cp config/server_template.json config/server.json
RUN touch alert.log

ENTRYPOINT ["/usr/bin/python3", "/opt/AlarmPI/run.py"]
