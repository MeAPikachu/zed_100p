#include <stdio.h>
#include "xparameters.h"
#include "netif/xadapter.h"
#include "platform_config.h"
#include "xil_printf.h"
#include "xtime_l.h"

#include "parameters.h"

#if LWIP_IPV6==1
#include "lwip/ip.h"
#else
#if LWIP_DHCP==1
#include "lwip/dhcp.h"
#endif
#endif

// AD4134 Libraries
#include <sleep.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "vitis/ad4134/spi_engine.h"
#include "vitis/ad4134/ad713x.h"
#include "vitis/ad4134/no_os_spi.h"
#include "vitis/ad4134/xilinx_spi.h"
#include "vitis/ad4134/no_os_delay.h"
#include "vitis/ad4134/no_os_gpio.h"
#include "vitis/ad4134/xilinx_gpio.h"
#include "vitis/ad4134/no_os_util.h"
#include "vitis/ad4134/no_os_error.h"
#include "vitis/ad4134/no_os_pwm.h"
#include "vitis/ad4134/axi_pwm_extra.h"
#include "vitis/ad4134/clk_axi_clkgen.h"
#include "vitis/ad4134/axi_dmac.h"

#include "xtime_l.h"
int main_thread();
void print_echo_app_header();
void open_connection(void *);

void lwip_init();
#if LWIP_IPV6==0
#if LWIP_DHCP==1
extern volatile int dhcp_timoutcntr;
err_t dhcp_start(struct netif *netif);
#endif
#endif

#define THREAD_STACKSIZE 1024

static struct netif server_netif;
struct netif *echo_netif;

extern uint8_t connection_disconnected;

struct no_os_spi_desc *spi_eng_desc;
struct spi_engine_offload_message spi_engine_offload_message;
struct spi_engine_offload_init_param spi_engine_offload_init_param;




// Buffer Definitions
aligned_buffers buffers[NUM_BUFFERS];
uint32_t buffer_store[BUFFER_STORE_SIZE] __attribute__((aligned(1024))) = {0};


volatile uint8_t buffer_idx = 0; // For buffer iterator
volatile uint8_t buffer_store_idx = 0;
//uint32_t adc_buffer_len = VALID_BYTES;

uint32_t i = 0, j;
int32_t ret;
const float lsb = 4.096 / (pow(2, 23));
float data;


int fill_buffer() {
	if (connection_disconnected) {
		ret = spi_engine_offload_init(spi_eng_desc, &spi_engine_offload_init_param);


		if (ret != 0) {
			xil_printf("Error initilializing SPI Engine offload");
		}

		connection_disconnected = 0;

	}
#if BUFFER_MODE == 0
	buffer_idx = 0;
	spi_engine_offload_message.rx_addr = buffers[buffer_idx].data;
	//spi_engine_offload_message.rx_addr = (uint32_t)adc_buffers[buffer_idx];
	ret = spi_engine_offload_transfer(spi_eng_desc, spi_engine_offload_message,
		        					  (AD4134_FMC_CH_NO * AD4134_FMC_SAMPLE_NO));
		if (ret != 0) {
		    return ret;
		}
#else
	#if TRANSFER_MODE == 0
	for (buffer_idx = 0; buffer_idx < NUM_BUFFERS; buffer_idx++) {
			uint32_t start_index = buffer_store_idx * (AD4134_FMC_CH_NO * AD4134_FMC_SAMPLE_NO);
			//printf("Start Index: %d\r\n", start_index);
			spi_engine_offload_message.rx_addr = &buffer_store[start_index];
			/*XTime time_start, time_end;
			XTime_GetTime(&time_start);*/
			ret = spi_engine_offload_transfer(spi_eng_desc, spi_engine_offload_message,
											  (AD4134_FMC_CH_NO * AD4134_FMC_SAMPLE_NO));
			//XTime_GetTime(&time_end);
			//printf("Offload Time: %lf s\r\n", ((double)(time_end - time_start) / (double)COUNTS_PER_SECOND));

			if (ret != 0) {
				printf("Error\r\n");
				return ret;
			}

			Xil_DCacheInvalidateRange((INTPTR)&buffer_store[start_index], SAMPLE_DATA * sizeof(uint32_t));
			buffer_store_idx += 1;
			//printf("Buffer Store Index: %d\r\n", buffer_store_idx);
		}
	#else
	for (buffer_idx = 0; buffer_idx < NUM_BUFFERS; buffer_idx++) {
		spi_engine_offload_message.rx_addr = buffers[buffer_idx].data;

		ret = spi_engine_offload_transfer(spi_eng_desc, spi_engine_offload_message,
			        					  (AD4134_FMC_CH_NO * AD4134_FMC_SAMPLE_NO));
		if (ret != 0) {
			return ret;
		}
	}
	#endif
#endif





	return 0;
}

int main()
{
	struct axi_clkgen *clkgen_4134;
	struct axi_clkgen_init clkgen_4134_init = {
		.base = XPAR_AXI_AD4134_CLKGEN_BASEADDR,
		.name = "ad4134_clkgen",
		.parent_rate = 100000000
	};
	struct ad713x_dev *ad713x_dev_1;
	//struct ad713x_dev *ad713x_dev_2;
	struct ad713x_init_param ad713x_init_param_1;
	uint32_t spi_eng_dma_flg = DMA_LAST | DMA_PARTIAL_REPORTING_EN;
	uint32_t spi_eng_msg_cmds[1];
	static struct xil_spi_init_param spi_engine_init_params = {
		.type = SPI_PS,
	};
	struct xil_gpio_init_param gpio_extra_param;
	struct no_os_gpio_init_param ad4134_1_dclkio = {
		.number = GPIO_DCLKIO_1,
		.platform_ops = &xil_gpio_ops,
		.extra = &gpio_extra_param
	};
	struct no_os_gpio_init_param ad4134_1_dclkmode = {
		.number = GPIO_DCLKMODE,
		.platform_ops = &xil_gpio_ops,
		.extra = &gpio_extra_param
	};
	struct no_os_gpio_init_param ad4134_1_mode = {
		.number = GPIO_MODE_1,
		.platform_ops = &xil_gpio_ops,
		.extra = &gpio_extra_param
	};
	struct no_os_gpio_init_param ad4134_1_pnd = {
		.number = GPIO_PDN_1,
		.platform_ops = &xil_gpio_ops,
		.extra = &gpio_extra_param
	};
	struct no_os_gpio_init_param ad4134_1_resetn = {
		.number = GPIO_RESETN_1,
		.platform_ops = &xil_gpio_ops,
		.extra = &gpio_extra_param
	};
	struct no_os_gpio_init_param ad4134_cs_sync = {
		.number = GPIO_CS_SYNC,
		.platform_ops = &xil_gpio_ops,
		.extra = &gpio_extra_param
	};
	struct spi_engine_init_param spi_eng_init_param  = {
		.type = SPI_ENGINE,
		.spi_engine_baseaddr = AD4134_SPI_ENGINE_BASEADDR,
		.cs_delay = 0,
		.data_width = 32,
		.ref_clk_hz = AD713x_SPI_ENG_REF_CLK_FREQ_HZ
	};
	const struct no_os_spi_init_param spi_eng_init_prm  = {
		.chip_select = AD4134_1_SPI_CS,
		.max_speed_hz = 50000000,
		.mode = NO_OS_SPI_MODE_1,
		.platform_ops = &spi_eng_platform_ops,
		.extra = (void*)&spi_eng_init_param,
	};

	struct no_os_pwm_desc *axi_pwm;
	struct axi_pwm_init_param axi_zed_pwm_init_trigger = {
		.base_addr = XPAR_ODR_GENERATOR_BASEADDR,
		.ref_clock_Hz = 100000000,
		.channel = 0
	};
	struct axi_pwm_init_param axi_zed_pwm_init_odr = {
		.base_addr = XPAR_ODR_GENERATOR_BASEADDR,
		.ref_clock_Hz = 100000000,
		.channel = 1
	};
	struct no_os_pwm_init_param axi_pwm_init_trigger = {
		.period_ns = 3000,//trig_period_ns,
		.duty_cycle_ns = 1,//trig_duty_cycle_ns,
		.phase_ns = 45,
		.platform_ops = &axi_pwm_ops,
		.extra = &axi_zed_pwm_init_trigger
	};
	struct no_os_pwm_init_param axi_pwm_init_odr = {
		.period_ns = 3000,//odr_period_ns,
		.duty_cycle_ns = 130,//odr_duty_cycle_ns,
		.phase_ns = 0,
		.platform_ops = &axi_pwm_ops,
		.extra = &axi_zed_pwm_init_odr
	};

	gpio_extra_param.device_id = GPIO_DEVICE_ID;

	gpio_extra_param.device_id = GPIO_DEVICE_ID;
	gpio_extra_param.type = GPIO_PS;

	ad713x_init_param_1.adc_data_len = ADC_24_BIT_DATA;
	ad713x_init_param_1.clk_delay_en = false;
	ad713x_init_param_1.crc_header = CRC_6;
	ad713x_init_param_1.dev_id = ID_AD4134;
	ad713x_init_param_1.format = QUAD_CH_PO;
	ad713x_init_param_1.gpio_dclkio = &ad4134_1_dclkio;
	ad713x_init_param_1.gpio_dclkmode = &ad4134_1_dclkmode;
	ad713x_init_param_1.gpio_mode = &ad4134_1_mode;
	ad713x_init_param_1.gpio_pnd = &ad4134_1_pnd;
	ad713x_init_param_1.gpio_resetn = &ad4134_1_resetn;
	ad713x_init_param_1.gpio_cs_sync = &ad4134_cs_sync;
	ad713x_init_param_1.mode_master_nslave = false; // Change to false if using external clock
	ad713x_init_param_1.dclkmode_free_ngated = false;
	ad713x_init_param_1.dclkio_out_nin = false;
	ad713x_init_param_1.pnd = true;
	ad713x_init_param_1.spi_init_prm.chip_select = AD4134_1_SPI_CS;
	ad713x_init_param_1.spi_init_prm.device_id = SPI_DEVICE_ID;
	ad713x_init_param_1.spi_init_prm.max_speed_hz = 10000000;
	ad713x_init_param_1.spi_init_prm.mode = NO_OS_SPI_MODE_0;
	ad713x_init_param_1.spi_init_prm.platform_ops = &xil_spi_ops;
	ad713x_init_param_1.spi_init_prm.extra = (void *)&spi_engine_init_params;
	ad713x_init_param_1.spi_common_dev = 0;


	spi_eng_msg_cmds[0] = READ(4);
	Xil_ICacheEnable();
	Xil_DCacheEnable();


	ret = axi_clkgen_init(&clkgen_4134, &clkgen_4134_init);
	if (ret != 0)
		return -1;

	ret = axi_clkgen_set_rate(clkgen_4134, AD713x_SPI_ENG_REF_CLK_FREQ_HZ);
	if (ret != 0)
		return -1;

	ret = no_os_pwm_init(&axi_pwm, &axi_pwm_init_trigger);
	if (ret != 0)
		return ret;

	ret = no_os_pwm_init(&axi_pwm, &axi_pwm_init_odr);
	if (ret != 0)
		return ret;


	ret = ad713x_init(&ad713x_dev_1, &ad713x_init_param_1);
	if (ret != 0)
		return -1;

	spi_engine_offload_init_param.rx_dma_baseaddr = AD4134_DMA_BASEADDR;
	spi_engine_offload_init_param.offload_config = OFFLOAD_RX_EN;
	spi_engine_offload_init_param.dma_flags = spi_eng_dma_flg;

	ret = no_os_spi_init(&spi_eng_desc, &spi_eng_init_prm);
	if (ret != 0)
		return -1;

	ret = spi_engine_offload_init(spi_eng_desc, &spi_engine_offload_init_param);
	if (ret != 0)
		return -1;

	spi_engine_offload_message.commands = spi_eng_msg_cmds;
	spi_engine_offload_message.no_commands = NO_OS_ARRAY_SIZE(spi_eng_msg_cmds);
	spi_engine_offload_message.commands_data = NULL;
	spi_engine_offload_message.rx_addr = buffers[buffer_idx].data;
	spi_engine_offload_message.tx_addr = 0xA000000;

	sys_thread_new("main_thrd", (void(*)(void*))main_thread, 0,
	                THREAD_STACKSIZE,
	                DEFAULT_THREAD_PRIO);
	vTaskStartScheduler();
	while(1);
	Xil_DCacheDisable();
	Xil_ICacheDisable();
	return 0;
}

void network_thread(void *p)
{
    struct netif *netif;
    unsigned char mac_ethernet_address[] = { 0x00, 0x0a, 0x35, 0x00, 0x01, 0x02 };
#if LWIP_IPV6==0
    ip_addr_t ipaddr, netmask, gw;
#if LWIP_DHCP==1
    int mscnt = 0;
#endif
#endif

    netif = &server_netif;

    xil_printf("\r\n\r\n");
    xil_printf("----- lwIP TCP Send-Once Server ------\r\n");

#if LWIP_DHCP==0
    IP4_ADDR(&ipaddr,  192, 168, 1, 10);
    IP4_ADDR(&netmask, 255, 255, 255,  0);
    IP4_ADDR(&gw,      192, 168, 1, 1);
    print_ip_settings(&ipaddr, &netmask, &gw);
#endif

#if LWIP_DHCP==1
	ipaddr.addr = 0;
	gw.addr = 0;
	netmask.addr = 0;
#endif

    if (!xemac_add(netif, &ipaddr, &netmask, &gw, mac_ethernet_address, PLATFORM_EMAC_BASEADDR)) {
		xil_printf("Error adding N/W interface\r\n");
		return;
    }

    netif_set_default(netif);
    netif_set_up(netif);

    sys_thread_new("xemacif_input_thread", (void(*)(void*))xemacif_input_thread, netif,
            THREAD_STACKSIZE, DEFAULT_THREAD_PRIO);

#if LWIP_DHCP==1
    dhcp_start(netif);
    while (1) {
		vTaskDelay(DHCP_FINE_TIMER_MSECS / portTICK_RATE_MS);
		dhcp_fine_tmr();
		mscnt += DHCP_FINE_TIMER_MSECS;
		if (mscnt >= DHCP_COARSE_TIMER_SECS*1000) {
			dhcp_coarse_tmr();
			mscnt = 0;
		}
	}
#else
    fill_buffer();

    print_echo_app_header();
    xil_printf("\r\n");
    sys_thread_new("echod", open_connection, 0,
		THREAD_STACKSIZE, DEFAULT_THREAD_PRIO);
    vTaskDelete(NULL);
#endif
    return;
}

int main_thread()
{
#if LWIP_DHCP==1
	int mscnt = 0;
#endif

	lwip_init();


	sys_thread_new("NW_THRD", network_thread, NULL,
		THREAD_STACKSIZE, DEFAULT_THREAD_PRIO);

#if LWIP_DHCP==1
    while (1) {
		vTaskDelay(DHCP_FINE_TIMER_MSECS / portTICK_RATE_MS);
		if (server_netif.ip_addr.addr) {
			xil_printf("DHCP request success\r\n");
			print_ip_settings(&(server_netif.ip_addr), &(server_netif.netmask), &(server_netif.gw));
			fill_buffer();
			print_echo_app_header();
			xil_printf("\r\n");
			sys_thread_new("echod", open_connection, 0,
					THREAD_STACKSIZE, DEFAULT_THREAD_PRIO);
			break;
		}
		mscnt += DHCP_FINE_TIMER_MSECS;
		if (mscnt >= DHCP_COARSE_TIMER_SECS * 2000) {
			xil_printf("ERROR: DHCP request timed out\r\n");
			xil_printf("Configuring default IP of 192.168.1.10\r\n");
			IP4_ADDR(&(server_netif.ip_addr),  192, 168, 1, 10);
			IP4_ADDR(&(server_netif.netmask), 255, 255, 255,  0);
			IP4_ADDR(&(server_netif.gw),  192, 168, 1, 1);
			print_ip_settings(&(server_netif.ip_addr), &(server_netif.netmask), &(server_netif.gw));
			fill_buffer();
			print_echo_app_header();
			xil_printf("\r\n");
			sys_thread_new("echod", open_connection, 0,
					THREAD_STACKSIZE, DEFAULT_THREAD_PRIO);
			break;
		}
	}
#endif
    vTaskDelete(NULL);
    return 0;
}

void print_ip(char *msg, ip_addr_t *ip)
{
	xil_printf(msg);
	xil_printf("%d.%d.%d.%d\n\r", ip4_addr1(ip), ip4_addr2(ip),
			ip4_addr3(ip), ip4_addr4(ip));
}

void print_ip_settings(ip_addr_t *ip, ip_addr_t *mask, ip_addr_t *gw)
{
	print_ip("Board IP: ", ip);
	print_ip("Netmask : ", mask);
	print_ip("Gateway : ", gw);
}
