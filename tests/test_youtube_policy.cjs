const assert = require('node:assert/strict');
const createPolicy = require('../youtube/assets/policy.js');

{
    const policy = createPolicy();
    const streamingData = {adaptiveFormats: [{url:'https://video.example/media',mimeType:'video/mp4'}]};
    const result = policy.clean({playabilityStatus:{status:'OK'},videoDetails:{videoId:'abcdefghijk'},
        streamingData,adPlacements:[{adPlacementRenderer:{}}],playerAds:[{}],adSlots:[{}]});
    assert.deepEqual(result.adPlacements, []);
    assert.deepEqual(result.playerAds, []);
    assert.deepEqual(result.adSlots, []);
    assert.equal(result.streamingData, streamingData);
    assert.deepEqual(result.playabilityStatus, {status:'OK'});
}
{
    const policy = createPolicy();
    const fixture = {contents:[{videoRenderer:{videoId:'regular'}},{adSlotRenderer:{}},
        {reelShelfRenderer:{items:[{reelItemRenderer:{}}]}},{videoRenderer:{videoId:'another'}}]};
    assert.deepEqual(policy.clean(fixture).contents.map(x => x.videoRenderer.videoId), ['regular','another']);
}
{
    const policy = createPolicy();
    const data = {contents:[{richItemRenderer:{content:{promotedVideoRenderer:{}}}},
        {richItemRenderer:{content:{videoRenderer:{videoId:'keep'}}}}]};
    assert.equal(policy.clean(data).contents.length, 1);
    assert.equal(data.contents[0].richItemRenderer.content.videoRenderer.videoId, 'keep');
}
{
    const policy = createPolicy();
    const guide = id => ({guideEntryRenderer:{navigationEndpoint:{browseEndpoint:{browseId:id}}}});
    const result = policy.clean([guide('FEwhat_to_watch'),guide('FEsubscriptions'),guide('FEhistory'),guide('FEshorts')]);
    assert.deepEqual(result.map(x => x.guideEntryRenderer.navigationEndpoint.browseEndpoint.browseId), ['FEsubscriptions','FEhistory']);
}
{
    const policy = createPolicy();
    const body = JSON.stringify({context:{client:{clientName:'TVHTML5'}},browseId:'FEwhat_to_watch',params:'home-only'});
    const updated = JSON.parse(policy.rewriteBody('https://www.youtube.com/youtubei/v1/browse?key=test',body,JSON.parse,JSON.stringify));
    assert.equal(updated.browseId, 'FEsubscriptions');
    assert.equal(updated.params, undefined);
    assert.equal(updated.context.client.clientName, 'TVHTML5');
    assert.equal(policy.rewriteBody('/youtubei/v1/player',body,JSON.parse,JSON.stringify), body);
}
{
    let observed;
    const policy = createPolicy(id => { observed = id; });
    policy.clean({videoDetails:{videoId:'abcdefghijk'},streamingData:{formats:[]}});
    assert.equal(observed, 'abcdefghijk');
    assert.doesNotThrow(() => policy.clean({contents:[null, 'plain text', 4, {newUnknownRenderer:{works:true}}]}));
}
console.log('6 YouTube response-policy checks passed; these do not prove live playback or ad removal.');
