QueryControl
============

The mission of QueryControl as a company is to get data to those who need it quickly. As an open source product, QueryControl will be middleware for various database engines to enable controlled data sharing on a grand scale. The first engine being developed for is Socrata. 

The core idea behind QueryControl is data owners such as government agencies would be more willing to allow outsiders to analyze their data within various limits if the outsiders couldn't access the underlying data.

## Warning about use of Socrata undocumented APIs

QueryControl uses undocumented Socrata APIs. 

## Examples

### Dataset of unredacted addresses firefighters/paramedics were dispatched to

At https://communities.socrata.com/dataset/QueryControl-filters-example/3meq-iszs is a dataset of query filters.

One of those filters is for Seattle Fire Department's dataset of addresses the fire department was dispatched to. The public dataset has unredacted addresses for every dispatch. For privacy reasons the Fire Department may decide it no longer wants to publish addresses. If it does so then per address grouping analysis would become impossible. But what if the fire department could allow ad hoc per address grouping analysis without giving out addresses or IDs that could be used to identify addresses. 

The filter:

`{"group_fields": ["address", "type", "datetime","report_location", "report_location_zip", "report_location_address"], "select_fields": ["type"]}`

Our filter allows us to count number of dispatch events per address as long as we don't ask for the addresses.

http://querycontrol.herokuapp.com/forsocrata/data.seattle.gov/grwu-wqtk.json/?$select=:group_count,:group_count%2F:total_count%20*%20100%20as%20percentage&$group=address&$order=:group_count%20DESC&$limit=10

`[{"count": "3354", "percentage": "0.64746159919540252100"}, {"count": "3166", "percentage": "0.61116977431504006600"}, {"count": "1829", "percentage": "0.35307312609671771300"}, {"count": "1775", "percentage": "0.34264887852469871000"}, {"count": "1683", "percentage": "0.32488904932792559400"}, {"count": "1213", "percentage": "0.23415948712701945700"}, {"count": "1206", "percentage": "0.23280819577509106700"}, {"count": "1180", "percentage": "0.22778911361078562100"}, {"count": "1158", "percentage": "0.22354219793329639800"}, {"count": "1061", "percentage": "0.20481716062800300400"}]`

Our filter doesn't allow us to ask for number of events per address if we are asking for the address.

http://querycontrol.herokuapp.com/forsocrata/data.seattle.gov/grwu-wqtk.json/?$select=address,:group_count&$group=address&$order=:group_count%20DESC&$limit=10

`{"error": "address not allowed in $select"}`







