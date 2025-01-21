# syntax=docker/dockerfile:1
# cross-platform, cpu-only dockerfile for demoing MWA software stack
# on amd64, arm64
# ref: https://docs.docker.com/build/building/multi-platform/
ARG BASE_IMG="ubuntu:20.04"
FROM ${BASE_IMG} as base

ENV LC_ALL=C
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt install -y \
    saods9 \
    csh \
    bzip2 \
    ffmpeg \
    bc \
    rsync \
    zip \
    git \
    wget \
    curl \
    pigz \
    stilts \
    graphviz-dev \
    xorg \
    xvfb \
    xz-utils \
    build-essential \
    groff \
    python3 \
    python3-pip \
    liberfa-dev \
    casacore-dev \
    casacore-tools \
    cmake \
    gfortran \
    libopenblas-dev \
    libcfitsio-dev \
    libfftw3-dev \
    libpng-dev \
    libxml++2.6-dev \
    python3-dev \
    python3-pip \
    default-libmysqlclient-dev \
    libgtkmm-3.0-dev \
    xorg \
    libhdf5-dev \
    libcairo2-dev \
    doxygen \
    libboost-dev \
    libgsl-dev \
    libboost-dev \
    liblua5.3-dev \
    mpich \
    python3-distutils \
    libblas-dev \
    liblapack-dev \
    libeigen3-dev \
    pybind11-dev \
    libboost-filesystem-dev \
    libboost-date-time-dev \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-program-options-dev \
    libboost-python-dev \
    libboost-test-dev \
    libgsl-dev \
    parallel \
    vim \
    autoconf \
    libtool \
    && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    apt-get -y autoremove


# Get Rust
ARG RUST_VERSION=stable
ENV RUSTUP_HOME=/opt/rust CARGO_HOME=/opt/cargo PATH="/opt/cargo/bin:${PATH}"
RUN mkdir -m755 $RUSTUP_HOME $CARGO_HOME && ( \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | env RUSTUP_HOME=$RUSTUP_HOME CARGO_HOME=$CARGO_HOME sh -s -- -y \
    --profile=minimal \
    --default-toolchain=${RUST_VERSION} \
    )

# use python3 as the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

RUN python -m pip install -U pip setuptools 

RUN python -m pip install --no-cache-dir \
    cython \
    scipy==1.6.1 \
    astropy \
    lmfit==1.0.3 \
    tifffile==2023.7.10 \
    jedi==0.18.1 \
    pandas==1.5.3 \
    numpy==1.20.3 \
    ;

RUN python -m pip install --no-cache-dir \
    ipython \
    numba \
    tqdm \
    matplotlib \
    astroquery \
    mysql-connector-python \
    pytest \
    h5py \
    scikit-image \
    scikit-learn \
    requests \
    pillow \
    seaborn \
    SQLAlchemy==1.4.49 \
    mysqlclient \
    reproject \
    ;




RUN python -m pip install --no-cache-dir \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://gitlab.com/Sunmish/flux_warp.git \
    git+https://github.com/tjgalvin/fits_warp.git \
    git+https://github.com/MWATelescope/mwa-calplots.git \
    git+https://github.com/ICRAR/manta-ray-client.git \
    git+https://github.com/tjgalvin/mwa_pb_lookup.git \
    git+https://github.com/GLEAM-X/GLEAM-X-pipeline.git \
    ;

# ------------------------------------------------
# mwa-reduce
# private repository found at: https://github.com/ICRAR/mwa-reduce
# ------------------------------------------------
COPY mwa-reduce /mwa-reduce
RUN cd / \
    && cd mwa-reduce \
    && mkdir build \
    && cd build \
    && cmake ../ \
    && make -j8 \
    && cd / \
    && mv mwa-reduce opt

# ------------------------------------------------
# AWS Command Line
# Used for the S3 bucket
# ------------------------------------------------

RUN cd / \
  && mkdir aws \
  && cd aws \
  && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
  && unzip awscliv2.zip \
  && ./aws/install \
  && cd /aws \ 
  && rm -r *.zip



# ------------------------------------------------
# MIRIAD 
# Used for regrid and convolve tasks
# NOTE: The command chaining is not performed
# ------------------------------------------------
RUN cd / \
    && wget ftp://ftp.atnf.csiro.au/pub/software/miriad/miriad-linux64.tar.bz2 -P / \
    && wget ftp://ftp.atnf.csiro.au/pub/software/miriad/miriad-common.tar.bz2 -P /
RUN bzcat miriad-linux64.tar.bz2 | tar xvf -  
RUN bzcat miriad-common.tar.bz2 | tar xvf -  
ENV MIR=/miriad 
RUN cd $MIR \  
    && sed -e "s,@MIRROOT@,$MIR," ./scripts/MIRRC.in > ./MIRRC \
    && sed -e "s,@MIRROOT@,$MIR," ./scripts/MIRRC.sh.in > ./MIRRC.sh
RUN chmod 644 $MIR/MIRRC*
RUN cd / \
    && rm -r *.bz2 


# ------------------------------------------------
# SWarp
# Modified version of swarp with an increased version of BIG,
# which was needed to avoid some regions of mosaic images 
# being blanked due to excessive weights
# ------------------------------------------------
RUN cd / \
    && git clone https://github.com/tjgalvin/swarp.git \
    && cd swarp \
    && git checkout big \
    && ./autogen.sh \
    && ./configure \
    && make \
    && make install \
    && cd / \
    && rm -r swarp

# ------------------------------------------------
# Sneaky symlink
# ------------------------------------------------
RUN cd / \
    && ln -s /usr/include 

# ------------------------------------------------
# WCSTools
# The latest version has a bug in getfits. Using 
# older version for this reason. 
# ------------------------------------------------
RUN cd / \
    && cd opt \
    && wget http://tdc-www.harvard.edu/software/wcstools/Old/wcstools-3.8.7.tar.gz \
    && tar xvfz wcstools-3.8.7.tar.gz \
    && cd ./wcstools-3.8.7 \
    && make -j8 \
    && cd /opt \
    && rm -r wcstools-3.8.7.tar.gz



# ------------------------------------------------
# CASA
# ------------------------------------------------
# Note second version defined in %environment needs to match
ARG version="release-5.7.0-134.el6"
RUN echo "Pulling CASA version ${version}"

RUN cd / \
    && cd opt \
    && wget http://casa.nrao.edu/download/distro/casa/release/el6/casa-"${version}".tar.gz \
    && tar -xf casa-"${version}".tar.gz \
    && rm -rf casa-"${version}".tar.gz

ENV PATH="${PATH}:/opt/casa-${version}/bin" 
RUN echo 'Updating casa data' \
    && casa-config --exec update-data

# Update casacore (from the apt install) with the updated measures as well
RUN rm -r /usr/share/casacore/data \
     && ln -s /opt/casa-release-5.7.0-134.el6/data /usr/share/casacore/data

RUN rm -r /var/lib/casacore/data \
     && ln -s /opt/casa-release-5.7.0-134.el6/data /var/lib/casacore/data
# ------------------------------------------------

# ------------------------------------------------
# WSClean
# ------------------------------------------------
RUN cd / \
    && wget https://www2.graphviz.org/Packages/stable/portable_source/graphviz-2.44.1.tar.gz \
    && tar -xvzf graphviz-2.44.1.tar.gz \
    && cd graphviz-2.44.1 \
    && ./configure \
    && make -j8 \
    && make install \
    && cd / \
    && rm -r graphviz-2.44.1 graphviz-2.44.1.tar.gz

ARG EVERYBEAM_BRANCH=v0.5.2
RUN git clone --depth 1 --branch=${EVERYBEAM_BRANCH} --recurse-submodules https://git.astron.nl/RD/EveryBeam.git /EveryBeam && \
    cd /EveryBeam && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make install -j`nproc` && \
    cd / && \
    rm -rf /EveryBeam

# ARG WSCLEAN_BRANCH=v2.9
# RUN git clone --depth 1 --branch=${WSCLEAN_BRANCH} https://gitlab.com/aroffringa/wsclean.git /wsclean && \
#     cd /wsclean && \
#     git submodule update --init --recursive && \
#     mkdir build && \
#     cd build && \
#     cmake .. && \
#     make install -j`nproc` && \
#     cd / && \
#     rm -rf /wsclean

RUN cd / \
    && git clone https://gitlab.com/aroffringa/wsclean.git \
    && cd wsclean \
    && git fetch \
    && git fetch --tags \
    && git checkout wsclean2.9 \
    && cd wsclean \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make -j8 \
    && make install \
    && cd ../.. \
    && cd chgcentre \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make -j8 \
    && make install \
    && cd / \
    && rm -rf wsclean

ARG AOFLAGGER_BRANCH=v3.4.0
RUN git clone --depth 1 --branch=${AOFLAGGER_BRANCH} --recurse-submodules https://gitlab.com/aroffringa/aoflagger.git /aoflagger && \
    cd /aoflagger && \
    mkdir build && \
    cd build && \
    cmake \
    -DENABLE_GUI=OFF \
    -DPORTABLE=ON \
    .. && \
    make install -j1 && \
    ldconfig && \
    cd / && \
    rm -rf /aoflagger

# ------------------------------------------------
# mwa_pb
# ------------------------------------------------
RUN cd / \
    && git clone "https://github.com/MWATelescope/mwa_pb.git" \
    && cd mwa_pb \
    && python setup.py install 

ARG BIRLI_BRANCH=main
RUN git clone --depth 1 --branch=${BIRLI_BRANCH} https://github.com/MWATelescope/Birli.git /Birli && \
    cd /Birli && \
    cargo install --path . --locked && \
    cd / && \
    rm -rf /Birli ${CARGO_HOME}/registry

ARG HYPERDRIVE_BRANCH=marlu0.13
RUN git clone --depth 1 --branch=${HYPERDRIVE_BRANCH} https://github.com/MWATelescope/mwa_hyperdrive.git /hyperdrive && \
    cd /hyperdrive && \
    cargo install --path . --locked && \
    cd / && \
    rm -rf /hyperdrive ${CARGO_HOME}/registry

# download latest Leap_Second.dat, IERS finals2000A.all
RUN python -c "from astropy.time import Time; t=Time.now(); from astropy.utils.data import download_file; download_file('http://data.astropy.org/coordinates/sites.json', cache=True); print(t.gps, t.ut1)"


# # ------------------------------------------------
# # Clean up
# # ------------------------------------------------
# RUN cd / \
#     && rm *gz
# ------------------------------------------------

# ------------------------------------------------
# CASA
# ------------------------------------------------
# CASA version needs to be specified here as well
ARG version="release-5.7.0-134.el6"
ENV PATH="${PATH}:/opt/casa-${version}/bin"
# ------------------------------------------------

# ------------------------------------------------
# WCSTools 
# ------------------------------------------------
ENV PATH="/opt/wcstools-3.8.7/bin:$PATH"
# ------------------------------------------------

# ------------------------------------------------
# mwa-reduce
# ------------------------------------------------
ENV PATH="/opt/mwa-reduce/build:$PATH"
# ------------------------------------------------

# ------------------------------------------------
# PB Lookup
# ------------------------------------------------
ENV MWA_PB_BEAM='/pb_lookup/gleam_xx_yy.hdf5'
ENV MWA_PB_JONES='/pb_lookup/gleam_jones.hdf5'
ENV PATH="/opt/mwa_pb/:$PATH"

# ------------------------------------------------

# ------------------------------------------------
#  MIRIAD
# THINK THIS NEEDS TWEAKING INSTEAD OF EXPORT TO USE ENV 
# ------------------------------------------------
RUN . /miriad/MIRRC.sh
ENV PATH=$MIRBIN:$PATH
# ------------------------------------------------

# ------------------------------------------------
# rust
# ------------------------------------------------
ENV LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib/:/usr/lib/x86_64-linux-gnu/"
ENV PATH=/opt/cargo/bin:$PATH
# ------------------------------------------------

