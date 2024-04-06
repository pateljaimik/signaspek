/*****************************************************************************
* | File      	:   OLED_1in51_test.c
* | Author      :   Waveshare team
* | Function    :   1.51inch OLED Module test demo
* | Info        :
*----------------
* |	This version:   V1.0
* | Date        :   2022-07-14
* | Info        :
* -----------------------------------------------------------------------------
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
******************************************************************************/
extern "C" {
    #include "test.h"
    #include "OLED_1in51.h"
    }
//-------------------------------------------Socket Communication-----------------------------------------------------------------------
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>

#define QUEUE_ELEM 1024

void enqueue(std::queue <std::string> &my_queue, std::mutex &my_mutex, std::condition_variable &my_cVar)
{
    //-------------------------------------------Socket Communication-----------------------------------------------------------------------
    int sockfd;
    struct sockaddr_un serv_addr;
    char buffer[1024];
    sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sockfd < 0) {
        perror("ERROR opening socket");
        exit(1);
    }
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sun_family = AF_UNIX;
    strcpy(serv_addr.sun_path, "/tmp/SignaSpek");
    if (connect(sockfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        perror("ERROR connecting");
        exit(1);
    }
   
    //-------------------------------------------Socket Communication-----------------------------------------------------------------------
    
    while(1)
    {	

	memset(buffer, 0, sizeof(buffer));
	ssize_t n = read(sockfd, buffer, sizeof(buffer) - 1);
	if (n < 0) {
		perror("ERROR reading from socket");
		exit(1);
	}
	//printf("Received: %s\n", buffer);
	std::unique_lock  <std::mutex> my_lock(my_mutex);
	while(my_queue.size() >= QUEUE_ELEM){
		my_cVar.wait(my_lock);
	}
	my_queue.push(buffer);
	my_cVar.notify_one();
	my_lock.unlock();
    }
    // Close the connection
    close(sockfd);

    // Remove the socket file
    unlink("/tmp/SignaSpek");
}

void dequeue(std::queue <std::string> &my_queue, char buffer[1024], std::mutex &my_mutex, std::condition_variable &my_cVar, int length)
{
    int start_size;
    int new_data_size;
    int x = 0;
    int available_space = 1024;
    char display_buffer[1024];
    int n = 1024;
    
    printf("1.51inch OLED test demo\n");
    if(DEV_ModuleInit() != 0) {
	//~ return -1;
	return;
    }
      
    printf("OLED Init...\r\n");
    OLED_1in51_Init();
    DEV_Delay_ms(500);
    OLED_1in51_Clear();	
    // 0.Create a new image cache
    UBYTE *BlackImage;
    UWORD Imagesize = ((OLED_1in51_WIDTH%8==0)? (OLED_1in51_WIDTH/8): (OLED_1in51_WIDTH/8+1)) * OLED_1in51_HEIGHT;
    if((BlackImage = (UBYTE *)malloc(Imagesize)) == NULL) {
		    printf("Failed to apply for black memory...\r\n");
		    //~ return -1;
		    return;
    }
    printf("Paint_NewImage\r\n");
    Paint_NewImage(BlackImage, OLED_1in51_WIDTH, OLED_1in51_HEIGHT, 270, BLACK);
    printf("Drawing\r\n");

    
    // Drawing on the image
//    printf("Drawing:page 2\r\n");     
    
    
    //char string[] = "This is a test of the OLED display, and how it looks like for long lines of text.";
    
    int i = 0;
    //char count for character scroll
    int charcount = 0;   
    while(1)
    {
	if(strlen(buffer) == 0)
	{
	    x = 126;
	}
	if(!my_queue.empty()){
	    std::unique_lock<std::mutex> my_lock(my_mutex);
    	    n = strlen(my_queue.front().c_str());
	    available_space = 1024 - strlen(buffer);
	    new_data_size = available_space < n ? available_space : n;
	    //strncat(buffer + strlen(buffer), buffer, new_data_size);    

	    strncpy(buffer + strlen(buffer), my_queue.front().c_str(), strlen(my_queue.front().c_str()));
	    my_queue.pop();
	    my_cVar.notify_one();
	    my_lock.unlock();
	}
	if(x > 0)
	{
	    Paint_DrawString_EN(x, 20, buffer, &Font12, WHITE, WHITE);
	    x = x-7;
	}

	else
	{
	    charcount++;
	    if(charcount%1 == 0){ strncpy(buffer, strcat(buffer+1, " \0"), strlen(buffer)); }//display_buffer+1, strlen(display_buffer)-1); }//strcat(display_buffer+1, " "), strlen(display_buffer)); }
	    Paint_DrawString_EN(0, 20, buffer, &Font12, WHITE, WHITE);
	}
	printf("size of display_buffer: %d\n", strlen(buffer));
	//~ printf("This is the display_buffer: %s\n", display_buffer);
	OLED_1in51_Display(BlackImage);
	if(x >=0) {DEV_Delay_ms(60);}
	else {DEV_Delay_ms(60);} 
	Paint_Clear(BLACK);
	i++;
    }

    OLED_1in51_Clear();
}

int OLED_1in51_test(void)
{        
    //------------------------------------------------ Threading ---------------------------------------------------------------------------
    std::thread t_enqueue;
    std::thread t_dequeue;
    char buffer[1024];// = "This is a test for queueing and threading.";
    std::queue <std::string> my_queue;
    std::mutex my_mutex;
    std::condition_variable my_cVar;
    char display_buffer[1024];
    int length = strlen(buffer);
    //------------------------------------------------ Threading ---------------------------------------------------------------------------
    
    t_enqueue = std::thread(enqueue,std::ref(my_queue), std::ref(my_mutex), std::ref(my_cVar));
    t_dequeue = std::thread(dequeue, std::ref(my_queue), display_buffer, std::ref(my_mutex), std::ref(my_cVar), length);
    t_enqueue.join();
    t_dequeue.join();    
	
    return 0;
}

