# Copyright (c) 2023 Graphcore Ltd. All rights reserved.import os
from git import Repo
from pathlib import Path


ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
CLONE_DIR = "path/to/clone/"
GITHUB_URL = f"https://{ACCESS_TOKEN}:x-oauth-basic@github.com/graphcore/Gradient-"


# Setup github url and repo names
repo_names = [
    "Pytorch-Geometric",
    "HuggingFace",
    "Pytorch",
    "Tensorflow2",
]
repo_urls = [GITHUB_URL + repo + "-private.git" for repo in repo_names]
clone_paths = [CLONE_DIR + repo for repo in repo_names]

# Make clone requests
for url, path in zip(repo_urls, clone_paths):
    Repo.clone_from(url, path)

# Find all paths to notebooks and notebook names
graphcore_notebook_names = []
for path in Path(CLONE_DIR).resolve().rglob("*.ipynb"):
    graphcore_notebook_names.append(path.stem)

print(graphcore_notebook_names)
