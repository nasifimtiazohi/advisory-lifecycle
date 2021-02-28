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
    name = 'snykids'
    start_urls = [
        'https://snyk.io/vuln'
        ]
    base_url = 'https://snyk.io'

    def joinText(self, selectors):
        ''' where text() gives multiple selectors with newlines and spaces, wrap and strip '''
        return ''.join(selectors).strip()

    def parse(self, response):
        
        advisory_table = response.xpath('/html/body/div[1]/main/div[5]/div/table')
        advisory_rows = advisory_table.xpath(".//tr")[1:]

        for row in advisory_rows:
            advisory = Advisory()

            links = row.xpath(".//a[starts-with(@href,'/vuln/')]")
            assert len(links) == 2 #one for the vulnerability, one for the package
            vuln_partial_url = links[0].xpath('@href').extract_first()
            advisory['vulId'] = vuln_partial_url[len('/vuln/'):]
            advisory['package'] = self.joinText(links[1].xpath('.//text()').extract())
            advisory['vulType'] = self.joinText(links[0].xpath('(.//text())').extract())
            advisory['severity'] = self.joinText(row.xpath(".//span[@class='severity-list__item-text']/text()").extract())
            advisory['versions'] = self.joinText(row.xpath(".//span[@class='semver']/text()").extract())
            advisory['ecosystem'] = self.joinText(row.xpath(".//td[@class='t--sm']")[1].xpath(".//text()").extract())   

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

        #TODO select the specifc card content
        headers = response.xpath(".//div[@class='card__content']/dl/dt")
        values = response.xpath(".//div[@class='card__content']/dl/dd")
        assert len(headers) == len(values)
        details = {}
        for i in range(0,len(headers)):
            details[self.joinText(headers[i].xpath('.//text()').extract())] = self.joinText(values[i].xpath('.//text()').extract())
        advisory['details'] = details

        #TODO wrong logic
        references = response.xpath(".//div[@class='card__content']/ul")[0].xpath(".//li")
        r = {}
        for e in references:
            r[self.joinText(e.xpath(".//text()").extract())] = self.joinText(e.xpath(".//a/@href").extract())
        advisory['references'] = r
        
        yield advisory

        


        