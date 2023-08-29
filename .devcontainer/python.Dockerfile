FROM python:3

WORKDIR /opt/timer

COPY requirements.txt /opt/timer/requirements.txt
COPY termdown.py /opt/timer/termdown.py

RUN python3 -m pip install --no-cache-dir -r requirements.txt


ENTRYPOINT [ "python", "/opt/timer/termdown.py" ]