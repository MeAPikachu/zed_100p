from multiprocessing import Process, Event
from client.dashboards import dashboard
from client.daq.daq import DAQ

################
# Board Config #
################
board_ip = "192.168.1.10"
port = 7
samples = 1024 * 40  # Must be consistent with the value set in parameters.h
channels = 4
limit_frames = True  # Enable limiting the number of downloaded frames
num_frames = 10  # Limit to # of frames

###############
# Data Config #
###############
timestamp_header = 0  # Timestamp header is work in progress. Leave at 0
file_name = "continuous-offload.hdf5"


stop_event = Event()


def collect_data(
    board_ip, port, samples, channels, timestamp_header, file_name, stop_event
):
    daq = DAQ(
        board_ip,
        port,
        samples,
        channels,
        timestamp_header,
        file_name,
        limit_frames,
        num_frames,
    )
    daq.init_hdf5()
    daq.run(stop_event)


if __name__ == "__main__":
    daq_process = Process(
        target=collect_data,
        args=(
            board_ip,
            port,
            samples,
            channels,
            timestamp_header,
            file_name,
            stop_event,
        ),
    )

    dashboard_process = Process(target=dashboard.create_dashboard, args=(file_name,))
    try:
        daq_process.start()
        dashboard_process.start()
        daq_process.join()
        dashboard_process.join()
    except KeyboardInterrupt:
        stop_event.set()
        daq_process.join()
        dashboard_process.terminate()
        dashboard_process.join()
