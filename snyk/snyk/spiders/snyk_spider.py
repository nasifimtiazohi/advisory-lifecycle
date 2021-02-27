import scrapy
import logging

class Advisory(scrapy.Item):
    vulId = scrapy.Field()
    vulType = scrapy.Field()
    severity = scrapy.Field()
    package = scrapy.Field()
    versions = scrapy.Field()
    ecosystem = scrapy.Field()
    score = scrapy.Field()
    vector = scrapy.Field()
    details = scrapy.Field()
    references = scrapy.Field()

class snykidsSpider(scrapy.Spider):
    ''' get the vulnerability IDs '''
    name = 'snykids'
    start_urls = [
        'https://snyk.io/vuln'
        ]
    base_url = 'https://snyk.io'

    def joinText(self, selectors):
        ''' where text() gives multiple selectors, wrap and strip '''
        return ''.join(selectors).strip()

    def parse(self, response):
        
        advisory_table = response.xpath('/html/body/div[1]/main/div[5]/div/table')
        advisory_rows = advisory_table.xpath(".//tr")[1:]
        # advisory_links = advisory_table.xpath(".//a[starts-with(@href,'/vuln/SNYK-')]/@href").extract()

        # for link in advisory_links:
        #     vulnLink = self.base_url + link
        #     yield scrapy.Request(vulnLink, callback=self.parse_vuln)
        #     break


        for row in advisory_rows:
            advisory = Advisory()

            links = row.xpath(".//a[starts-with(@href,'/vuln/')]")
            assert len(links) == 2
            vuln_partial_url = links[0].xpath('@href').extract_first()
            advisory['vulId'] = vuln_partial_url[len('/vuln/'):]
            advisory['package'] = links[1].xpath('.//text()').extract_first()
            advisory['vulType'] = links[0].xpath('(.//text())').extract()[1]
            advisory['severity'] = row.xpath(".//span[@class='severity-list__item-text']/text()").extract_first()
            advisory['versions'] = row.xpath(".//span[@class='semver']/text()").extract_first()
            advisory['ecosystem'] = row.xpath(".//td[@class='t--sm']")[1].xpath(".//text()").extract_first().strip()    

            vuln_url = self.base_url + vuln_partial_url
            yield scrapy.Request(vuln_url, callback=self.parse_vuln, meta={'item': advisory})

            #yield advisory #why does this not work here
        
        return

        if  len(response.xpath(".//a[@class='pagination__next']/@href")) > 0: 
            next_page_url = self.base_url + response.xpath(".//a[@class='pagination__next']/@href").extract_first()
            yield scrapy.Request(next_page_url,callback=self.parse)

        
    def parse_vuln(self, response):

        def extractIfPresentElseNone(selector, xpath):
            try:
                return selector.xpath(xpath).extract_first()
            except Exception as e:
                logging.debug(e)
                return None

        advisory = response.meta['item']
        advisory['score'] = extractIfPresentElseNone(response, ".//div[contains(@class,'cvss-breakdown__score')]/text()")
        advisory['vector'] = extractIfPresentElseNone(response, ".//div[contains(@class,'cvss-breakdown__vector')]/text()")

        headers = response.xpath(".//div[@class='card__content']/dl/dt")
        values = response.xpath(".//div[@class='card__content']/dl/dd")
        assert len(headers) == len(values)
        details = {}
        for i in range(0,len(headers)):
            details[self.joinText(headers[i].xpath('.//text()').extract())] = self.joinText(values[i].xpath('.//text()').extract())
        advisory['details'] = details

        references = response.xpath(".//div[@class='card__content']/ul")[0].xpath(".//li")
        r = {}
        for e in references:
            r[e.xpath(".//text()").extract_first().strip()]= e.xpath(".//a/@href").extract_first()
        advisory['references'] = r
        
        yield advisory

        


        