FROM ubuntu:18.04
MAINTAINER fabien@fleutot.net

ENV USER balloon

EXPOSE 80/tcp

RUN useradd ${USER}
WORKDIR /home/${USER}
RUN chown ${USER} /home/${USER}
RUN chmod a+rX /home/${USER}

# Avoid interactive questions during tzdata setup
RUN ln -s /usr/share/zoneinfo/UTC /etc/localtime

# Ubuntu packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        gcc python3 python3-pip python3-setuptools python3-dev ipython3 \
        nodejs npm \
        python3-grib libeccodes-tools \
        libdpkg-perl \
        nginx cron \
        less emacs-nox apt-utils mlocate && \
    apt-get clean

# Python packages
# TODO Probably some superfluous packages to get rid of
ENV PYTHONPATH /home/${USER}/backend
RUN pip3 install wheel
RUN pip3 install\
    Django\
    django-cors-headers\
    django-extensions\
    ipython\
    ipython-genutils\
    psycopg2\
    psycopg2-binary\
    python-dateutil\
    pytz\
	requests\
    uwsgi

# Node.js packages
COPY frontend/package.json frontend/package.json
RUN cd frontend && npm install

RUN mkdir -p backend html/static log
COPY balloon backend/balloon
COPY core backend/core
COPY forecast backend/forecast
COPY manage.py backend/manage.py
RUN backend/manage.py collectstatic --noinput --link

# Generate / collect Node.js static files
COPY frontend frontend
RUN mkdir -p html
RUN cd frontend && node_modules/.bin/webpack
RUN cd html && ln -s ../frontend/dist/* ../frontend/static/* .

# Configure services
COPY conf conf

RUN cat conf/append-to-bashrc.sh >> /root/.bashrc && \
    crontab conf/${USER}.cron

RUN ln -s /home/${USER}/conf/nginx.conf /etc/nginx/sites-available/${USER}.conf && \
    ln -s ../sites-available/${USER}.conf /etc/nginx/sites-enabled/ && \
    rm -rf /etc/nginx/sites-enabled/default /var/www/html && \
    echo "website root in /home/${USER}/html" > /var/www/README.txt

RUN backend/manage.py migrate && \
	backend/manage.py forecast_terrain

ENTRYPOINT /home/${USER}/conf/entrypoint.sh
