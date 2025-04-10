# syntax=docker/dockerfile:1
# cross-platform, cpu-only dockerfile for demoing MWA software stack
# on amd64, arm64
# ref: https://docs.docker.com/build/building/multi-platform/
# TODO: perhaps add mwa_pb to python path? 
# Also need to figure out issue with wcstools 

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

RUN python -m pip install -U pip setuptools==70.0.0 

RUN python -m pip install --no-cache-dir \
    cython==3.0.10 \
    scipy==1.6.1 \
    astropy \
    lmfit==1.0.3 \
    tifffile==2021.8.30 \
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


# RUN python -m pip install -U pip setuptools 

# RUN python -m pip install --no-cache-dir \
#     cython \
#     scipy==1.6.1 \
#     astropy \
#     lmfit==1.0.3 \
#     tifffile==2023.7.10 \
#     jedi==0.18.1 \
#     pandas==1.5.3 \
#     numpy==1.20.3 \
#     ;

# RUN python -m pip install --no-cache-dir \
#     asciitree==0.3.3 \
#     asteval==0.9.25 \
#     astropy==5.0.4\
#     astropy-healpix==0.6 \
#     astroquery==0.4.7 \
#     asttokens==2.0.5 \
#     backcall==0.2.0 \
#     beautifulsoup4==4.12.3 \
#     black==22.1.0 \
#     blinker==1.4 \
#     casatools==6.4.0.16 \
#     certifi==2019.11.28 \
#     chardet==3.0.4 \
#     click==8.0.3 \
#     cmasher==1.6.3 \
#     colorama==0.4.6 \
#     colorspacious==1.1.2 \
#     contourpy==1.1.1 \
#     cryptography==2.8 \
#     cycler==0.12.1 \
#     Cython==3.0.10 \
#     dask==2023.5.0 \
#     dbus-python==1.2.16 \
#     debugpy==1.5.1 \
#     decorator==5.1.1 \
#     distro==1.4.0 \
#     docstring-parser==0.16 \
#     e13tools==0.9.6 \
#     entrypoints==0.3 \
#     exceptiongroup==1.2.1 \
#     executing==0.8.3 \
#     fasteners==0.19 \
#     fonttools==4.51.0 \
#     fsspec==2024.5.0 \
#     future==0.18.2 \
#     greenlet==3.0.3 \
#     h5py \
#     healpy==1.15.0 \
#     html5lib==1.1 \
#     httplib2==0.14.0 \
#     idna==2.8 \
#     imageio==2.34.1 \
#     importlib-metadata==7.1.0 \
#     importlib-resources==6.4.0 \
#     iniconfig==2.0.0 \
#     ipykernel==6.9.2 \
#     ipython==8.1.1 \
#     jedi==0.18.1 \
#     joblib==1.1.0 \
#     jupyter-client==7.1.2 \
#     jupyter-core==4.9.2 \
#     keyring==18.0.1 \
#     kiwisolver==1.4.5 \
#     launchpadlib==1.10.13 \
#     lazr.restfulclient==0.14.2 \
#     lazr.uri==1.0.3 \
#     lazy-loader==0.4 \
#     llvmlite==0.41.1 \
#     lmfit==1.0.3 \
#     locket==1.0.0 \
#     matplotlib==3.7.5 \
#     matplotlib-inline==0.1.3 \
#     mccabe==0.6.1 \
#     mypy-extensions==0.4.3 \
#     mysql-connector-python==8.4.0 \
#     mysqlclient==2.2.4 \
#     nest-asyncio==1.5.4 \
#     networkx==3.1 \
#     numba==0.58.1 \
#     numcodecs==0.12.1 \
#     numpy==1.22.0 \
#     oauthlib==3.1.0 \
#     packaging==24.0 \
#     pandas==1.5.3 \
#     parso==0.8.3 \
#     partd==1.4.1 \
#     pathspec==0.9.0 \
#     pexpect==4.9.0 \
#     pickleshare==0.7.5 \
#     pillow==10.3.0 \
#     platformdirs==2.4.1 \
#     pluggy==1.5.0 \
#     prompt-toolkit==3.0.43 \
#     psutil==5.9.8 \
#     ptyprocess==0.7.0 \
#     pure-eval==0.2.2 \
#     pycodestyle==2.8.0 \
#     pycosat==0.6.3 \
#     pydocstyle==6.1.1 \
#     pyerfa==2.0.0.3 \
#     pyflakes==2.4.0 \
#     Pygments==2.11.2 \
#     PyGObject==3.36.0 \
#     PyJWT==1.7.1 \
#     pylama==8.3.6 \
#     pyparsing==3.1.2 \
#     pytest==8.2.1 \
#     python-apt \
#     python-casacore \
#     python-dateutil==2.9.0.post0 \
#     pytz==2024.1 \
#     pyuvdata==2.4.2 \
#     pyvo==1.5.1 \
#     PyWavelets==1.4.1 \
#     PyYAML==6.0.1 \
#     pyzmq==22.3.0 \
#     reproject==0.8 \
#     requests==2.22.0 \
#     requests-unixsocket==0.2.0 \
#     ruamel.yaml==0.17.20 \
#     ruamel.yaml.clib==0.2.6 \
#     scikit-image==0.21.0 \
#     scikit-learn==1.0.2 \
#     scipy==1.6.1 \
#     seaborn==0.13.2 \
#     SecretStorage==2.3.1 \
#     setuptools-scm==8.1.0 \
#     simplejson==3.16.0 \
#     six==1.14.0 \
#     snowballstemmer==2.2.0 \
#     soupsieve==2.5 \
#     SQLAlchemy==2.0.30 \
#     stack-data==0.2.0 \
#     systemd-python==234 \
#     threadpoolctl==3.0.0 \
#     tifffile==2023.7.10 \
#     tomli==2.0.0 \
#     toolz==0.12.1 \
#     tornado==6.1 \
#     tqdm==4.62.3 \
#     traitlets==5.1.1 \
#     typing-extensions==4.0.1 \
#     uncertainties==3.1.6 \
#     urllib3==1.25.8 \
#     wadllib==1.3.3 \
#     wcwidth==0.2.13 \
#     webencodings==0.5.1 \
#     websocket-client==1.8.0 \
#     zarr==2.16.1 \
#     zipp==3.18.2 \
#     ;




RUN python -m pip install --no-cache-dir \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://gitlab.com/Sunmish/flux_warp.git \
    git+https://github.com/tjgalvin/fits_warp.git \
    git+https://github.com/MWATelescope/mwa-calplots.git \
    git+https://github.com/ICRAR/manta-ray-client.git \
    git+https://github.com/astrokatross/mwa_pb_lookup.git \
    git+https://github.com/GLEAM-X/GLEAM-X-pipeline.git \
    git+https://github.com/MWATelescope/mwa_pb.git \
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
    && make \
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

# Might need to specify v0.13.0 to make it work 
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

ARG GIANTSQUID_BRANCH=main
RUN git clone --depth 1 --branch=${GIANTSQUID_BRANCH} https://github.com/MWATelescope/giant-squid.git /Giant-Squid && \
    cd /Giant-Squid && \
    cargo install --path . --locked && \
    cd / && \
    rm -rf /Giant-Squid ${CARGO_HOME}/registry

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

