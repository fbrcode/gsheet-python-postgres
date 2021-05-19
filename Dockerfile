FROM python:3.8-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk --no-cache add bash musl-dev linux-headers g++ postgresql-dev python3-dev openblas-dev

COPY requirements.txt /usr/src
ADD ./src /usr/src
WORKDIR /usr/src

RUN pip install -r requirements.txt

CMD [ "python", "google-sheets.py" ]
