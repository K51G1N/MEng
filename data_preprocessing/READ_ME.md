# Installation and SOMA setup

I have been exhausted trying to install SOMA and mix and match dependencies and using WSL and windows was an incredible strugggle. With all these conflicts I tried to get as close to possible to the initial release of [SOMA](https://github.com/nghorbani/soma)

I have been working through this slowly and have had gemini as my side 


## Ubuntu 

I tried to do a live usb boot but it was slow and infuriating. I decided to partition 64 GB on my SSD and then boot from the live usb and do an install.

### USB Boot

I downloaded the Ubuntu 20.04.6 LTS from the [Ubuntu website](https://releases.ubuntu.com/20.04.6/?_gl=1*19ip6hm*_gcl_au*MTE4NTIyOTI0MS4xNzA3MTMxMDQx&_ga=2.149898549.2084151835.1707729318-1126754318.1683186906) and selected the *Desktop image*

This then downloads a .iso file

I then utilised a tool called Rufus to flash the USB, 

Side note: In my case I forgot to allocate persistent memory for the usb. It might not be necessary for the installation onto a partitian but it can be useful to have a quick USB boot to go and to store files 

### Create Partitian: 

I had to go on windows disk manager, select my drive and the portion, right click and shrink volume.

### Ubuntu USB to partitian
The install on the USB to the Partitian I had to boot up into linux one can usually do F12, Del, ESC keys to get into the BIOS or select the appropriate settings

Once you've booted up into Linux using your iso image/USB then you will be able to run the installer it should be an icon/shortcut either in favourites or on the desktop

1. Identify the partitian
2. Select the root structure /
3. I then had to select the drive itself
4. I could then click install


What I did was I setup a partition on my ssd and installed ubuntu 

```keagan@keagan-Precision-3650-Tower:~$ lsb_release -a
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04.6 LTS
Release:	20.04
Codename:	focal
keagan@keagan-Precision-3650-Tower:~$ 

```

## Conda
I am now going to install conda mini 

I logged in with my google account and downloaded Miniconda `Miniconda3-latest-Linux-x86_64.sh`

In my downloads I ran `bash Miniconda3-latest-Linux-x86_64.sh`

You have to go through their legal notice about 11 returns/enters
then type yes

```
Miniconda3 will now be installed into this location:
/home/keagan/miniconda3

Proceed with initialization? [yes|no]
[no] >>> yes

```

I had ti then refresh my bashrc

```
keagan@keagan-Precision-3650-Tower:~/Downloads$ source ~/.bashrc
(base) keagan@keagan-Precision-3650-Tower:~/Downloads$ 
```
I ran `conda deactivate`

Then followed it up with `conda create -n soma python=3.7`

as we can then create our own virtual environment with python3.7

I then ran `conda activate soma` this will be the environment we do everything in from now on.

I ram `python --version` and got   `Python 3.7.16` which is what we would want to see

### System update and files

`sudo apt update`

We will need the gcc and g++ for later to compile so let's in

```
(soma) keagan@keagan-Precision-3650-Tower:~/Downloads$ gcc --version && g++ --version

Command 'gcc' not found, but can be installed with:

sudo apt install gcc

(soma) keagan@keagan-Precision-3650-Tower:~/Downloads$ sudo apt update
[sudo] password for keagan: 
Hit:1 http://security.ubuntu.com/ubuntu focal-security InRelease                                        
Hit:2 http://za.archive.ubuntu.com/ubuntu focal InRelease                                               
Hit:3 http://dell.archive.canonical.com focal InRelease                                                 
Hit:4 http://za.archive.ubuntu.com/ubuntu focal-updates InRelease   
Hit:5 http://za.archive.ubuntu.com/ubuntu focal-backports InRelease
Get:6 https://dl.google.com/linux/chrome/deb stable InRelease [1,825 B]
Get:7 https://dl.google.com/linux/chrome/deb stable/main amd64 Packages [1,217 B]
Fetched 3,042 B in 3s (888 B/s)       
Reading package lists... Done
Building dependency tree       
Reading state information... Done
392 packages can be upgraded. Run 'apt list --upgradable' to see them.
(soma) keagan@keagan-Precision-3650-Tower:~/Downloads$ sudo apt install gcc g++
```

Here we checked to see if we had gcc and g++, we then did the sudo apt update and then the install of gcc and g++

A quick check running `gcc --version && g++ --version`
```
(soma) keagan@keagan-Precision-3650-Tower:~/Downloads$ gcc --version && g++ --version
gcc (Ubuntu 9.4.0-1ubuntu1~20.04.2) 9.4.0
Copyright (C) 2019 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

g++ (Ubuntu 9.4.0-1ubuntu1~20.04.2) 9.4.0
Copyright (C) 2019 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

```

Since we want to clone the soma repo we need to first ensure that git is active 

Git was not installed can check `git --version` so I ran the `sudo apt install git` command and a quick check reveals 

```
(soma) keagan@keagan-Precision-3650-Tower:~/Downloads$ git --version
git version 2.25.1
```
## SOMA and Dependencies

I wemt to my Documents, made a new directory meng and then cd meng and
with git installed I ran `git clone https://github.com/nghorbani/soma.git`

Because the repository last updated the requirements in October of 2021 I decided to ask Gemini if we could create a requirements freeze for the 2021 date and ensure we still use those versions instead of breaking it. We then had to find specific commit hashes and later the requirements_2021.txt contents will be shown.


Interesting and so leaving it here for now. I am trying to be very cautious and ensure that when we hit a snag or an issue we can trace it and find what went wrong.

Okay so I ran 

`sudo apt install libatlas-base-dev libtbb2`

I then ran 

`conda install -c conda-forge ezc3d=1.4.4 numpy=1.21.2` 
I ran this because I went to see what version of ezc3d was out at the time to ensure we are not installing the latest version 

### NVIDIA cards and cuda

Gemini wanted me to run the nvidia-smi command to ensure we could leverage the RTX 3090

```
nvidia-smi
                                                                                                         
Command 'nvidia-smi' not found, but can be installed with:                                               
                                                                                                         
sudo apt install nvidia-340               # version 340.108-0ubuntu5.20.04.2, or                         
sudo apt install nvidia-utils-390         # version 390.157-0ubuntu0.20.04.1                             
sudo apt install nvidia-utils-450-server  # version 450.248.02-0ubuntu0.20.04.1                          
sudo apt install nvidia-utils-470         # version 470.256.02-0ubuntu0.20.04.1                          
sudo apt install nvidia-utils-470-server  # version 470.256.02-0ubuntu0.20.04.1                          
sudo apt install nvidia-utils-535         # version 535.183.01-0ubuntu0.20.04.1                          
sudo apt install nvidia-utils-535-server  # version 535.230.02-0ubuntu0.20.04.3
sudo apt install nvidia-utils-550-server  # version 550.144.03-0ubuntu0.20.04.1
sudo apt install nvidia-utils-570-server  # version 570.86.15-0ubuntu0.20.04.5
sudo apt install nvidia-utils-565-server  # version 565.57.01-0ubuntu0.20.04.2
sudo apt install nvidia-utils-435         # version 435.21-0ubuntu7
sudo apt install nvidia-utils-440         # version 440.82+really.440.64-0ubuntu6
sudo apt install nvidia-utils-418-server  # version 418.226.00-0ubuntu0.20.04.2

(soma) keagan@keagan-Precision-3650-Tower:~/Documents/meng/soma$ lspci | grep -i nvidia
01:00.0 VGA compatible controller: NVIDIA Corporation Device 2204 (rev a1)
01:00.1 Audio device: NVIDIA Corporation Device 1aef (rev a1)
```

Gemini warned me that 

```
Your hardware ID 2204 identifies your GPU as an NVIDIA GeForce RTX 3090. This is an Ampere-architecture card, which has a very specific requirement: it does not support CUDA versions older than 11.0.

If you try to use the cu102 (CUDA 10.2) version of PyTorch, your GPU will either not be detected or will throw a "no kernel image is available" error during runtime.
```

I consulted with Claude as well to ensure we weren't making mistakes

```
For RTX 3090 + PyTorch 1.8.2, here's the situation:
The RTX 3090 (Ampere architecture, compute capability 8.6) requires CUDA 11.0 minimum. CUDA 10.2 won't work.
PyTorch 1.8.2 LTS was released with these CUDA options:

cu102 (CUDA 10.2)
cu111 (CUDA 11.1)


Bottom line:
Go with the simpler approach:
bash

sudo apt install nvidia-driver-535 nvidia-utils-535
pip3 install torch==1.8.2+cu111 torchvision==0.9.2+cu111 torchaudio==0.8.2 -f https://download.pytorch.org/whl/lts/1.8/torch_lts.html

```

Having double checked with Claude and Gemini I was happy to proceed with the code

It told me to restart so I decided to restart/reboot my machine to load the nvidia driver

I saved my files and prepared for the reboot before running

`sudo reboot`

after rebooting the system I rand the `nvidia-smi` command and got the following information

```
(base) keagan@keagan-Precision-3650-Tower:~$ nvidia-smi
Tue Feb 10 21:16:08 2026       
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.230.02             Driver Version: 535.230.02   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA GeForce RTX 3090        Off | 00000000:01:00.0  On |                  N/A |
| 30%   38C    P8              28W / 350W |    464MiB / 24576MiB |      2%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
                                                                                         
+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A      1460      G   /usr/lib/xorg/Xorg                          170MiB |
|    0   N/A  N/A      1775      G   /usr/bin/gnome-shell                        154MiB |
|    0   N/A  N/A      3473      G   /proc/self/exe                               29MiB |
|    0   N/A  N/A      3743      G   ...cess-track-uuid=3190708988185955192       95MiB |
+---------------------------------------------------------------------------------------+
(base) keagan@keagan-Precision-3650-Tower:~$ conda activate soma
```

This was pleasant and good to see

From the reboot I had to activate my cond soma environment again

`conda activate soma`

There was a possible warning to ensure that we had the correct pip/pip3 and that it pointed to the same file 

```
(base) keagan@keagan-Precision-3650-Tower:~$ conda activate soma
(soma) keagan@keagan-Precision-3650-Tower:~$ pip3 --version
pip 22.3.1 from /home/keagan/miniconda3/envs/soma/lib/python3.7/site-packages/pip (python 3.7)
(soma) keagan@keagan-Precision-3650-Tower:~$ which pip
/home/keagan/miniconda3/envs/soma/bin/pip
(soma) keagan@keagan-Precision-3650-Tower:~$ which pip3
/home/keagan/miniconda3/envs/soma/bin/pip3

```
With that peace of mind we could install

Then finally the cuda and PyTorch install 

`pip install torch==1.8.2+cu111 torchvision==0.9.2+cu111 torchaudio==0.8.2 -f https://download.pytorch.org/whl/lts/1.8/torch_lts.html`

### Requirements.txt

Upon further validation with claude and gemini we could hunt for and find the appropriate commit hashes 

here is the contents of requirements_2021.txt

```
# --- Remote Git Dependencies ---
git+https://github.com/nghorbani/human_body_prior.git@SOMA
git+https://github.com/nghorbani/body_visualizer.git@fe4e5e8
git+https://github.com/nghorbani/configer.git@8cd1e3e556d9697298907800a743e120be57ac36

# --- Core Scientific Stack (Oct 2021 Versions) ---
numpy==1.21.2
scipy==1.7.1
pandas==1.3.3
scikit-learn==1.0
scikit-image==0.18.3
matplotlib==3.4.3
seaborn==0.11.2

# --- Deep Learning & 3D (Specific to SOMA/Body Prior) ---
pytorch-lightning==1.4.9
trimesh==3.9.30
chumpy==0.70
c3d==0.3.0

# --- Utilities & Tools ---
omegaconf==2.1.1
loguru==0.5.3
tqdm==4.62.3
opencv-python==4.5.3.56
pillow==8.3.2
imageio==2.9.0
xlsxwriter==3.0.1
tables==3.6.1
notifiers==1.2.0
toolz==0.11.1
six==1.16.0
pyOpenSSL==21.0.0

# --- Environment & Interface ---
jupyterlab==3.1.14
ipython==7.28.0
markdown==3.3.4
pycodestyle==2.7.0
setuptools==58.2.0
wheel==0.37.0
```

So with that file the next step was to get pytorch3d 

Initially it wanted me to download it from fb but it wasn't working 

so we ran `pip install fvcore iopath`

We then 

`pip install "git+https://github.com/facebookresearch/pytorch3d.git@v0.6.1"`


I had no issues and it took a short while to compile from source

We tested the compilation by 

```
python -c "import torch; import pytorch3d.renderer; print(f'GPU Name: {torch.cuda.get_device_name(0)}'); print(f'PyTorch3D CUDA Check: {torch.cuda.is_available()}')"
```

Success now it's on to the smpl-fast-derivatives

### smpl fast derivatives

I downloaded the [fast derivatives](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=smpl-fast-derivatives.tar.bz2)

You'll need a [SOMA account](https://soma.is.tue.mpg.de/)


Navigate to where it was downloaded and you can combine these or do them separately

`tar -xjvf smpl-fast-derivatives.tar.bz2`

`mv psbody ~/miniconda3/envs/soma/lib/python3.7/site-packages/`

or

`tar -xjvf smpl-fast-derivatives.tar.bz2 && mv psbody ~/miniconda3/envs/soma/lib/python3.7/site-packages/`

I did the former

### psbody.mesh library installation

I first check to see if the Boost libs were there

`sudo apt install libboost-dev libboost-serialization-dev`

Once all that checks out navigate to your directory

containing soma but not inside it

in my case `~/Documents/meng`

I then the following commands ensuring that the soma conda environment is active, `conda activate soma`,  


The python setup.py install gave us an issue because it packaged everything into an .egg

We should've instead used `python setup.py develop` for the instruction below

```
git clone https://github.com/MPI-IS/mesh.git
cd mesh
python setup.py install
```

`develop`

The fix:

1. identify where the egg is

python -c "import psbody.mesh; print(psbody.mesh.__file__)"

2. Move the SMPL Derivatives into the Egg

Move your existing smpl folder into the psbody directory inside that Egg. (Note: Replace the Egg name below with the specific version found in Step 1).

```
EGG_PATH="~/miniconda3/envs/soma/lib/python3.7/site-packages/psbody_mesh-0.4-py3.7-linux-x86_64.egg"

mv ~/miniconda3/envs/soma/lib/python3.7/site-packages/psbody/smpl $EGG_PATH/psbody/
```

3. Verify the unified namespace

`python -c "import psbody.mesh; import psbody.smpl; print('SUCCESS: Namespace collision resolved.')"`

### Blender installation 

1. Run this snap command to install Blender

`sudo snap install blender --channel=2.83lts/stable --classic`

2. confirm the blender version 

`blender --version`

we need to navigate to the ~/Downloads folder

3. extract the bpy, 

`tar -xjvf bpy-2.83-20200908.tar.bz2`

4. Move contents to soma site-packages

`mv bpy.so ~/miniconda3/envs/soma/lib/python3.7/site-packages/`

`mv 2.83 ~/miniconda3/envs/soma/lib/python3.7/site-packages/`

**Why this approach?**

Gemini said:

Why this specific approach?
Standard Blender usually contains its own internal Python. However, for research code like SOMA, we want to run Blender inside your existing Python environment.

The bpy.so is the actual shared library that allows you to run import bpy in a Python script.

The 2.83 folder contains the "internal guts" (scripts, data files, and shaders) that Blender needs to function once it's imported.


I tried to verify 

`python -c "import bpy; print(f'Blender-Python Version: {bpy.app.version_string}')"`

however got an error

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ImportError: libfftw3.so.3: cannot open shared object file: No such file or directory
```

I then had to update and install:

```
sudo apt update 
sudo apt install libfftw3-dev libsndfile1
```
running the verification again and out came `Blender-Python Version: 2.83.5`

### MoSh++

This is the mocap solver

One needs to get the smpl-x models and they can be found [here](https://download.is.tue.mpg.de/download.php?domain=smplx&sfile=smplx_locked_head.tar.bz2)



1. Let's install these packages C++ libraries used for geometric distance calculations 

`sudo apt install libtbb-dev libeigen3-dev`

2. Install MoSh++ core

```
cd ~/Documents/meng
git clone https://github.com/nghorbani/moshpp.git
cd moshpp

# Activate environment if not already
conda activate soma
```
Before we install the requirements I froze them again

```
# --- MoSh++ & SOMA Pinned Requirements ---
git+https://github.com/nghorbani/human_body_prior.git@SOMA
chumpy==0.70
scikit-learn==1.0
numpy==1.21.2
matplotlib==3.4.3
opencv-python==4.5.3.56
loguru==0.5.3
cython==0.29.24
```
Then finally we replace or simply create our own requirements file with it's own name in the moshpp directory

**Install requirements**
`pip install -r requirements_2021.txt`

3. Compile the mesh_distance engine


`cd src/moshpp/scan2mesh/mesh_distance`

then we `make`

Return to the moshpp root
`cd ../../../..`
or

`~/Documents/meng/moshpp`


4. Linking MoSh++ 

Keeping in mind our egg struggle from earlier we avoid it this time by using `develop`

`python setup.py develop`


one can validate it by

```
python -c "import moshpp; from moshpp.scan2mesh.mesh_distance import sample2meshdist; print('SUCCESS: MoSh++ solver engine is fully operational')"
```

And we should see: **SUCCESS: MoSh++ solver engine is fully operational**


### Returning to SOMA tutorials

As found [here](https://github.com/nghorbani/soma/tree/main/src/tutorials)

They provide a template folder structure for SOMA, [template](https://download.is.tue.mpg.de/soma/tutorials/SOMA_FOLDER_TEMPLATE.tar.bz2)
First, extract the official folder structure and rename it for clarity.

```
cd ~/Documents/meng/soma
tar -xjvf ~/Downloads/SOMA_FOLDER_TEMPLATE.tar.bz2 -C .
mv SOMA_FOLDER_TEMPLATE support_base
```

links:

1. Populate SMPL-X (Locked Head) [Download SMPL-X with removed head bun (NPZ+PKL, 830 MB) - Use this for SOMA/MoSh/AMASS codebase](https://download.is.tue.mpg.de/download.php?domain=smplx&sfile=smplx_locked_head.tar.bz2)

We are explicitly told to use this for SOMA/MoSh/AMASS data
You can extract it with the command
`tar -xjvf ~/Downloads/smplx_locked_head.tar.bz2 -C ~/Documents/meng/soma/support_base/support_files/smplx/`

2. Populate VPoser v2.0 [VPoser v2.0](https://download.is.tue.mpg.de/download.php?domain=smplx&sfile=V02_05.zip)

```
# 1. Create the target folder
mkdir -p ~/Documents/meng/soma/support_base/support_files/vposer_v2_0

# 2. Unzip to a temporary folder
unzip ~/Downloads/V02_05.zip -d ~/Downloads/vposer_temp

# 3. Move the contents (snapshots and .yaml)
mv ~/Downloads/vposer_temp/V02_05/* ~/Documents/meng/soma/support_base/support_files/vposer_v2_0/

# 4. Cleanup
rm -rf ~/Downloads/vposer_temp
```
3. Populate SMPL-H (Hand Model) [SMPL-H](https://download.is.tue.mpg.de/download.php?domain=mano&resume=1&sfile=smplh.tar.xz)

```
# 1. Create the neutral target folder
mkdir -p ~/Documents/meng/soma/support_base/support_files/smplh/neutral

# 2. Extract to Downloads temporary folder
mkdir -p ~/Downloads/smplh_temp
tar -xvf ~/Downloads/smplh.tar.xz -C ~/Downloads/smplh_temp

# 3. Move the neutral model and rename it to 'model.npz'
mv ~/Downloads/smplh_temp/neutral/model.npz ~/Documents/meng/soma/support_base/support_files/smplh/neutral/model.npz

# 4. Cleanup
rm -rf ~/Downloads/smplh_temp
```

4. Populate Extra SMPL-X Data [Extra smplx data](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=smplx/extra_smplx_data.tar.bz2)

This contains the pose_hand_prior.npz and APose.npz which are critical for the solver to initialize correctly.

`tar -xjvf ~/Downloads/extra_smplx_data.tar.bz2 -C ~/Documents/meng/soma/support_base/support_files/smplx/`

Final verification

`find ~/Documents/meng/soma/support_base/support_files -maxdepth 3 -not -path '*/.*'`


### MoSh Results

I realised I left out the MoSh Results containing c3d, scans and objects

```
mkdir -p ~/Documents/meng/soma/support_base/support_files/mosh_results

# 2. Extract directly into it
# (If it's a ZIP)
unzip ~/Downloads/MoSh_results.zip -d ~/Documents/meng/soma/support_base/support_files/mosh_results/

# 3. Organize (The zip often creates a nested 'MoSh_results' folder)
# We want the content (c3d, scans) to sit directly inside the support folder
mv ~/Documents/meng/soma/support_base/support_files/mosh_results/MoSh_results/* ~/Documents/meng/soma/support_base/support_files/mosh_results/
rmdir ~/Documents/meng/soma/support_base/support_files/mosh_results/MoSh_results
```

### Training experiement data for Tutorials

1. Populate Training Experiments (V48_02_SOMA)

First download them: [V48_02_SOMA](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=training_experiments/V48_02_SOMA.tar.bz2)
```
# Extract V48_02_SOMA (The Experiment Model)
# Assuming filename is V48_02_SOMA.tar.bz2
tar -xjvf ~/Downloads/V48_02_SOMA.tar.bz2 -C ~/Documents/meng/soma/support_base/training_experiments/
```
2. Populate Data (V48_01_SOMA)
First download them: [Data](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=smplx/data/V48_01_SOMA.tar.bz2)
```
# Extract V48_01_SOMA (The Dataset ID)
# Assuming filename is V48_01_SOMA.tar.bz2
tar -xjvf ~/Downloads/V48_01_SOMA.tar.bz2 -C ~/Documents/meng/soma/support_base/data/
```

[Body parameters without CAESAR betas](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=smplx/training_body_parameters/body_dataset.tar.bz2)


[Extra SMPL-X data](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=smplx/extra_smplx_data.tar.bz2)
[SSM head marker covariances](https://download.is.tue.mpg.de/soma/ssm_head_marker_corr.npz)
[Blend files](https://download.is.tue.mpg.de/download.php?domain=soma&sfile=blender/blend_files.tar.bz2)

### Running the solve_labeled_mocap.ipynb

I had to make some changes for my setup to their original data one of which was to the blend files

```
(soma) keagan@keagan-Precision-3650-Tower:~/Documents/meng/soma/support_base/support_files$ find . -name "*.blend"
./att_weights_transparent.blend
./soma_standard.blend
```

mkdir -p blender/blend_files
mv *.blend blender/blend_files/
ls blender/blend_files/
att_weights_transparent.blend  soma_standard.blend

I had to install ffmpeg