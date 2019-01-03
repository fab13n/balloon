#!/usr/bin/env bash

DIR="$(cd $(dirname $0) && pwd)"
NAME=balloon
EXPORT_TO_PORT=8765

docker stop $NAME -t 2
docker rm $NAME;
if [[ "$1" == "-r" ]]; then
	(cd $DIR && docker build . -t $NAME)
fi

docker run -d \
    --name $NAME \
    --publish $EXPORT_TO_PORT:80 \
	--volume $DIR/frontend:/home/$NAME/frontend \
	--volume $DIR/core:/home/$NAME/backend/core \
	--volume $DIR/forecast:/home/$NAME/backend/forecast \
	--volume $DIR/balloon:/home/$NAME/backend/balloon \
	--volume $DIR/install:/home/$NAME/install \
	--volume $DIR/data:/home/$NAME/data \
	--volume $DIR/log:/home/$NAME/log \
    $NAME

docker logs -f $NAME

