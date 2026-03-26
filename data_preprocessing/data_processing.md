# Data Processing

For our animation data pipeline we utilised the [SUMediPose dataset](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/GRRROM) best viewed using the tree view. We downloaded the `WCS/S*/*.json` data

The schema for the data is found in my file `sumedipose.schema.json` if you'd like to have it.

The process can be viewed as follows:

[ convert_json_to_c3d `.json` to `.c3d`] > [batch_prime `.c3d` ] > [batch_multi_solve `.c3d` to `.pkl`] > [batch_convert_npz_rectified `.pkl` to `.npz` ]

The requirements can be found in reqs.txt
The entire environment and linux setup can be found using the READ underscore ME file

It can be confusing trying to find all the files needed to download to make the support_base folder so I have added them to a [google drive folder](https://drive.google.com/drive/folders/1ERuzKHjXNrfc40TmKLjheeg5ftxe84vA?usp=sharing). You will need to request access, otherwise you are welcome to to the various sites and download and construct the folder structure yourself

You can find it distributed in MoSh, SOMA, SMPL-X. There are probably a few others. 





