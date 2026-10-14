FROM ghcr.io/cirruslabs/flutter@sha256:46691e311715845de03a3ba4753a475476936805b29431b1f00f1816981033f8
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 xvfb libgtk-3-dev clang cmake ninja-build pkg-config && rm -rf /var/lib/apt/lists/*
COPY bootstrap/pubspec.yaml /opt/eval-bootstrap/pubspec.yaml
RUN cd /opt/eval-bootstrap && flutter pub get && flutter config --enable-linux-desktop && flutter precache --linux --web
WORKDIR /work/repo
