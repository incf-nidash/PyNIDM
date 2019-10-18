import os
from setuptools import setup, find_packages
PACKAGES = find_packages()

# Get version and release info, which is all stored in nidm/version.py
ver_file = os.path.join('nidm', 'version.py')
with open(ver_file) as f:
    exec(f.read())

opts = dict(name=NAME,
            maintainer=MAINTAINER,
            maintainer_email=MAINTAINER_EMAIL,
            description=DESCRIPTION,
            long_description=LONG_DESCRIPTION,
            url=URL,
            download_url=DOWNLOAD_URL,
            license=LICENSE,
            classifiers=CLASSIFIERS,
            author=AUTHOR,
            author_email=AUTHOR_EMAIL,
            version=VERSION,
            packages=PACKAGES,
            scripts=SCRIPTS,
            install_requires=INSTALL_REQUIRES,
            #requires=INSTALL_REQUIRES,
            entry_points='''
               [console_scripts]
               pynidm=nidm.experiment.tools.click_main:cli
            '''
)



if __name__ == '__main__':
    setup(**opts)
