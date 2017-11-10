const search = (client, params, callback) => {
  const callParams = {
    ResponseGroup: 'ItemAttributes,Images,SalesRank'  // need SalesRank??
  }
  let op = 'ItemSearch'
  if (params.keywords) {
    callParams.Keywords = params.keywords
    // callParams.SearchIndex = params.searchindex || 'Books'
    callParams.SearchIndex = params.searchindex || 'All'
  } else if (params.itemid) {
    callParams.ItemId = params.itemid
    op = 'ItemLookup'
  } else {
    throw new Error('Neither keywords or itemid')
  }
  // XXX turn this into a promise instead
  return client.call(op, callParams, callback)
}

module.exports = { search }
