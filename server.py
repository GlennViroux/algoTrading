import socket
import threading
import utils
import glob
import os

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5050
ADDR = (SERVER,PORT)

HEADER=64
FORMAT='utf-8'
DISCONNECT_MSG="!DISCONNECT"
CONFIRMATION_MSG="Message received."
SERVER_OUTPUT_DIR_LOG="./output/SERVER_LOG_{}.txt".format(utils.date_now_filename())
MODE="SERVER"

def handle_client(conn,addr):
    utils.write_output_formatted(MODE,f"[NEW CONNECTION] {addr} connected.",SERVER_OUTPUT_DIR_LOG)
    connected=True
    while connected:
        pre_msg_header=conn.recv(HEADER)
        msg_header=pre_msg_header.decode(FORMAT)
        conn.send(CONFIRMATION_MSG.encode(FORMAT))

        if msg_header.strip():
            header_elems=msg_header.split('-')
            msg_cat=header_elems[0].strip()
            msg_type=header_elems[1].strip()
            
            if msg_cat=="SEND":
                msg_size=int(header_elems[2].strip())
                if msg_type=="TEXT":
                    msg=conn.recv(msg_size).decode(FORMAT)
                    conn.send(CONFIRMATION_MSG.encode(FORMAT))

                    utils.write_output_formatted(MODE,"Received text message: {}".format(msg),SERVER_OUTPUT_DIR_LOG)

                    if msg==DISCONNECT_MSG:
                        connected=False

                elif msg_type=="FILE":
                    data=utils.receive_chunks(conn,msg_size)
                    conn.send(CONFIRMATION_MSG.encode(FORMAT))

                    filename=msg_header.split('-')[3].strip()
                    with utils.safe_open(f"./{filename}",'wb') as f:
                        f.write(data)
                        
                    utils.write_output_formatted(MODE,"Received file {}".format(filename),SERVER_OUTPUT_DIR_LOG)

            elif msg_cat=="REQUEST":
                if msg_type=="LOG":
                    logpath=utils.get_latest_log()

                    if logpath:
                        msg="True"
                        msg_send=b' '*(HEADER-len(msg))+msg.encode(FORMAT)
                        conn.send(msg_send)

                        with open(logpath,'rb') as f:
                            logdata=f.read()

                        logdata_size=str(len(logdata)).encode(FORMAT)
                        logdata_size += b' ' * (HEADER-len(logdata_size))
                        conn.send(logdata_size)
                        utils.send_chunks(conn,logdata)
                        utils.write_output_formatted(MODE,"Sent log file {}".format(logpath),SERVER_OUTPUT_DIR_LOG)
                    else:
                        msg="False"
                        msg_send=b' '*(HEADER-len(msg))+msg.encode(FORMAT)
                        conn.send(msg_send)

                elif msg_type=="PLOT":
                    ticker=header_elems[2].strip()
                    plot=utils.get_plot(ticker)

                    if plot:
                        msg="True"
                        msg_send=b' '*(HEADER-len(msg))+msg.encode(FORMAT)
                        conn.send(msg_send)
                        with open(plot,'rb') as f:
                            plotdata=f.read()

                        plotdata_size=str(len(plotdata)).encode(FORMAT)
                        plotdata_size += b' ' * (HEADER-len(plotdata_size))
                        conn.send(plotdata_size)
                        utils.send_chunks(conn,plotdata)
                        utils.write_output_formatted(MODE,"Sent plot {}".format(utils.get_plot(ticker)),SERVER_OUTPUT_DIR_LOG)            
                    else:
                        msg="False"
                        msg_send=b' '*(HEADER-len(msg))+msg.encode(FORMAT)
                        conn.send(msg_send)


    utils.write_output_formatted(MODE,f"Closing connection with {addr}.",SERVER_OUTPUT_DIR_LOG)      
    conn.close()

def start():
    utils.write_output_formatted(MODE,f"Server {SERVER} is starting...",SERVER_OUTPUT_DIR_LOG)
    server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    server.bind(ADDR)
    server.listen()
    utils.write_output_formatted(MODE,f"Server is listening on {SERVER}",SERVER_OUTPUT_DIR_LOG) 

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client,args=(conn,addr))
        thread.start()
        utils.write_output_formatted(MODE,f"Active connections: {threading.activeCount()-1}",SERVER_OUTPUT_DIR_LOG)