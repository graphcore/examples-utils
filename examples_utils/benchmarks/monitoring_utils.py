# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
from typing import List, Dict
from pathlib import Path
import json
import datetime

try:
    import pandas as pd

    # while not used explicitely need to check
    from matplotlib import pyplot as plt
except (ImportError, ModuleNotFoundError) as error:
    from . import _incorrect_requirement_variant_error

    raise _incorrect_requirement_variant_error from error


def process_monitoring_file(file):
    file_content: List[Dict[str, Dict]] = [json.loads(l) for l in file.read_text().splitlines()]
    for entry in file_content:
        for i, card in enumerate(entry.pop("cards")):
            entry[f"cards.{i}"] = card
            for j, ipu in enumerate(card.pop("ipus")):
                card[f"ipus.{j}"] = ipu
    df = pd.json_normalize(file_content)
    pid_columns = [c for c in df.columns if ".PID" in c]
    df["ipus_in_use"] = df[pid_columns].notna().sum(axis="columns")
    df = df.set_index(pd.to_datetime(df["timestamp"], format="%Y-%m-%d-%H.%M.%S.%f"))
    return df


def plot_ipu_usage(directory: Path):
    directory = Path(directory)
    plot_gc_monitor(directory)
    plot_benchmark_utilisation(directory)


def plot_gc_monitor(directory: Path):
    monitoring_files = [*directory.rglob("ipu-monitor.jsonl")]
    fig, ax = plt.subplots(1, 1)
    for file in monitoring_files:
        df = process_monitoring_file(file)
        ax = df.plot(y="ipus_in_use", ax=ax, label=file.parent.name)

    ax.set_ylabel("Number of IPUs in use")
    leg = ax.legend()
    leg.set_bbox_to_anchor((1, -0.25))
    fig.savefig(directory / "ipu_usage.png", dpi=300, bbox_extra_artists=(leg,), bbox_inches="tight")
    return ax.figure


def process_utilisation_file(file: Path):
    def calculate_memory(x):
        try:
            m = (
                float(x["max active code size (bytes)"])
                + float(x["max active data size (bytes)"])
                + float(x["max active stack size (bytes)"])
            ) * 100 / (1472 * 624 * 1024)
        except:
            m = 0
        if pd.isna(m):
            m = 0
        return m
    data = []
    lines = file.read_text().splitlines()
    for i, l in enumerate(lines):
        try:
            data.append(json.loads(l))
        except Exception as error:
            print(f"{i} / {len(lines)}")
            print(l[-100:])
            print(error)

    df = pd.DataFrame(
        {
            (f"ipu-{innerKey}", datetime.datetime.fromisoformat(timestamp)): values
            for _, innerDict in enumerate(data)
            for timestamp, outerDict in innerDict.items()
            for innerKey, values in outerDict.items()
        }
    ).transpose()
    df.loc[:, "utilisation"] = (df.loc[:, "ipu utilisation"].str.strip("%")).map(float)
    df["memory_utilisation"] = df.apply(calculate_memory, axis="columns")
    df["attached"] = df.apply(
        lambda x: int(not pd.isna(x["user executable"])),
        axis="columns",
    )
    utilisation_summary = df[["utilisation", "memory_utilisation", "attached"]].groupby(level=1).sum()
    return df, utilisation_summary


def plot_benchmark_utilisation(directory: Path):
    directory = Path(directory)
    monitoring_files = [*directory.rglob("ipu-metrics.jsonl")]
    fig_summary, axs = plt.subplots(3, 1)
    for file in monitoring_files:
        df, summary = process_utilisation_file(file)
        fig = plot_full_utilisation(df)
        fig.savefig(file / "ipu_metrics.png", dpi=300, bbox_inches="tight")
        for ax, field in zip(axs, ["utilisation", "memory_utilisation", "attached"]):
            ax = summary.plot(y=field, ax=ax, label=file.parent.name)

    axs[0].set_ylabel("IPU activity (%)")
    axs[1].set_ylabel("Memory used (%)")
    axs[2].set_ylabel("IPU attached (T/F)")
    for ax in axs:
        leg = ax.legend()
    leg.set_bbox_to_anchor((1, -0.25))
    fig_summary.savefig(
        directory / "ipu_usage.png", dpi=300, bbox_extra_artists=[ax.legend() for ax in axs], bbox_inches="tight"
    )

    return ax.figure


def plot_full_utilisation(df):
    fig, axs = plt.subplots(3, 1)
    fig.set_size_inches(10, 15)

    ax = axs[0]
    ax.set_ylabel("IPU activity (%)")
    for ipu in df.index.get_level_values(0).unique():
        ax = df.loc[ipu].plot(y="utilisation", label=ipu, ax=ax)
    ax.legend().set_bbox_to_anchor((1, 1))

    ax = axs[1]
    ax.set_ylabel("Memory used (%)")
    for ipu in df.index.get_level_values(0).unique():
        ax = df.loc[ipu].plot(y="memory_utilisation", label=ipu, ax=ax)
    ax.legend().set_bbox_to_anchor((1, 1))

    ax = axs[2]
    ax.set_ylabel("IPU attached (T/F)")
    for ipu in df.index.get_level_values(0).unique():
        ax = df.loc[ipu].plot(y="attached", label=ipu, ax=ax)
    ax.legend().set_bbox_to_anchor((1, 1))
    return fig
