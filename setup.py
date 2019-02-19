import setuptools
import aer

setuptools.setup(
        name='aerpy',
        version=aer.VERSION_STR,
        description='a python library for reading ".aedat" format for event-camera logs.',
        author='Keisuke Sehara',
        url='https://github.com/gwappa/python-aerpy',
        packages=setuptools.find_packages(),
        install_requires=["numpy"],
        license="MIT",
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Development Status :: 4 - Beta",
            "Intended Audience :: Science/Research"
        ])
