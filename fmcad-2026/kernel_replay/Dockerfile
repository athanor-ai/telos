FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential autotools-dev autoconf automake libtool pkg-config \
      protobuf-compiler libprotobuf-dev libssl-dev libxcb-present-dev libcairo2-dev \
      libpango1.0-dev iptables dnsmasq-base apache2-bin apache2-dev ssl-cert \
      iperf3 iproute2 python3 python3-pip curl ca-certificates bc \
    && make-ssl-cert generate-default-snakeoil --force-overwrite \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ravinet/mahimahi.git /opt/mahimahi \
 && cd /opt/mahimahi \
 && ./autogen.sh \
 && ./configure \
 && make -j$(nproc) \
 && make install

WORKDIR /app
COPY run_sweep.py /app/
COPY ack_schedule.py /app/
COPY README.md /app/

CMD ["python3", "/app/run_sweep.py"]
