# Copyright (c) 2023 Graphcore Ltd. All rights reserved.import json
import datetime
import gcipuinfo
import time


def get_metrics():
    discovery_mode = gcipuinfo.DiscoverActivePartitionIPUs
    inventory = gcipuinfo.gcipuinfo(discovery_mode)
    inventory.setUpdateMode(True)
    all_data = json.loads(inventory.getDevicesAsJSON())
    print(json.dumps({datetime.datetime.utcnow().isoformat(): all_data}))


if __name__ == "__main__":

    try:
        while True:
            get_metrics()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
