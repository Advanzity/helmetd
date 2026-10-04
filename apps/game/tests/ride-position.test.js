import {test} from 'node:test';
import assert from 'node:assert/strict';
import {rideCoordinates,requestRideOrigin} from '../src/ride-position.js';
test('game movement offsets the browser origin, not a live GPS fix',()=>{
 const anchor={x:10,z:20,latitude:42,longitude:-83,accuracy:50};
 assert.equal(rideCoordinates({x:10,z:20},anchor).latitude,42);
 assert.ok(rideCoordinates({x:110,z:-80},anchor).latitude>42);
 assert.ok(rideCoordinates({x:110,z:-80},anchor).longitude>-83);
 assert.equal(rideCoordinates({x:0,z:0},null),null);
});
test('denied location leaves the game usable',async()=>{
 await assert.rejects(requestRideOrigin({x:0,z:0},{getCurrentPosition:(ok,fail)=>fail()}),/game position remains active/);
});
