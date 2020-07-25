import socket
import utils

SERVER="192.168.0.21"
PORT=5050
ADDR=(SERVER,PORT)

FORMAT='utf-8'
HEADER=64
CONFIRMATION_MSG="Message received."
CONFIRMATION_MSG_SIZE=17

client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
client.connect(ADDR)


def send_text(msg):
    message=msg.encode(FORMAT)
    msg_length=len(message)
    send_length=("SEND-TEXT-"+str(msg_length)).encode(FORMAT)
    send_length += b' ' * (HEADER-len(send_length))

    client.send(send_length)
    answer=client.recv(CONFIRMATION_MSG_SIZE).decode(FORMAT)
    if not answer==CONFIRMATION_MSG:
        return None

    client.send(message)
    answer=client.recv(CONFIRMATION_MSG_SIZE).decode(FORMAT)
    if not answer==CONFIRMATION_MSG:
        return None

    return True

def send_file(file_path):
    '''
    This function sends a file to the server, following TCP. 
    First a message containing the size of the file and the filename
    is sent to the server, and if a correct response is received, the 
    complete file is also sent.
    '''
    # Opening and reading file
    myfile=open(file_path,'rb')
    file_bytes=myfile.read()
    myfile.close()
    file_size=len(file_bytes)

    # Send file size to server
    filename=file_path.split("/")[-1]
    send_header=("SEND-FILE-"+str(file_size)+f"-{filename}").encode(FORMAT)
    send_header += b' ' * (HEADER-len(send_header))
    client.send(send_header)
    answer=client.recv(CONFIRMATION_MSG_SIZE).decode(FORMAT)
    if not answer==CONFIRMATION_MSG:
        return None

    # Send file to server
    utils.send_chunks(client,file_bytes)

    answer=client.recv(2048).decode(FORMAT)
    if not answer==CONFIRMATION_MSG:
        return None

    return True

def request_log(output_path):
    '''
    This functions tries to obtain the latest log file from the server.
    '''
    send_header="REQUEST-LOG".encode(FORMAT)
    send_header += b' ' * (HEADER-len(send_header))

    client.send(send_header)
    answer=client.recv(CONFIRMATION_MSG_SIZE).decode(FORMAT)
    if not answer==CONFIRMATION_MSG:
        client.close()
        return None

    log_size=int(client.recv(HEADER).decode(FORMAT))

    try:
        logfile_bytes=utils.receive_chunks(client,log_size)
    except RuntimeError:
        client.close()
        return None

    utils.safe_write(logfile_bytes,output_path,'wb')

    return True

def request_plot(stock,output_path):
    '''
    This functions tries to obtain the latest log file from the server.
    '''
    send_header="REQUEST-PLOT-{}".format(stock.upper()).encode(FORMAT)
    send_header += b' ' * (HEADER-len(send_header))

    client.send(send_header)
    answer=client.recv(CONFIRMATION_MSG_SIZE).decode(FORMAT)
    if not answer==CONFIRMATION_MSG:
        client.close()
        return None

    plot_size=client.recv(HEADER).decode(FORMAT)
    plot_size_int=int(plot_size)

    try:
        plot_bytes=utils.receive_chunks(client,plot_size_int)
    except RuntimeError:
        client.close()
        return None

    utils.safe_write(plot_bytes,output_path,'wb')
    return True
    

send_text("Hello world!")
send_file("/Users/glennviroux/Documents/Acct_101.pdf")
request_log("./client_log_output/output_log.txt")
request_plot("SAM","./client_log_output/SAM.png")
send_text("!DISCONNECT")

