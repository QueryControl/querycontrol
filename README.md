QueryControl
============

QueryControl will be middleware for various database engines. The first engine being developed for is Socrata.

The core idea behind QueryControl is data owners such as government agencies would be more willing to allow outsiders to analyze their data if the outsiders couldn't access the underlying data.

At https://communities.socrata.com/dataset/QueryControl-filters-example/3meq-iszs is a dataset of query filters.

One of those filters is for Seattle Fire Department's dataset of addresses the fire department was dispatched to. The public dataset has unredacted addresses for every dispatch. For privacy reasons the Fire Department may decide it no longer wants to publish addresses. If it does so then per address grouping analysis would become impossible. But what if the fire department could allow ad hoc per address grouping analysis without giving out addresses or IDs that could be used to identify addresses. 

Our filter allows us to count number of dispatch events per address as long as we don't ask for the addresses.

http://querycontrol.herokuapp.com/forsocrata/data.seattle.gov/grwu-wqtk.json/?$select=:group_count&$group=address&$order=:group_count%20DESC&$limit=10

Our filter doesn't allow us to ask for number of events per address if we are asking for the address.

http://querycontrol.herokuapp.com/forsocrata/data.seattle.gov/grwu-wqtk.json/?$select=address,:group_count&$group=address&$order=:group_count%20DESC&$limit=10







