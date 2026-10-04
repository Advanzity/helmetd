// An optional real-world anchor; movement continues to come exclusively from the game.
export function rideCoordinates(p,anchor){
 if(!anchor)return null;
 const lat=anchor.latitude-(p.z-anchor.z)/111320;
 return {latitude:lat,longitude:anchor.longitude+(p.x-anchor.x)/(111320*Math.max(.01,Math.cos(anchor.latitude*Math.PI/180))),accuracy:anchor.accuracy,source:'game-relative'};
}
export function requestRideOrigin(p,geolocation=navigator.geolocation){
 return new Promise((resolve,reject)=>{
  if(!geolocation)return reject(Error('Location unavailable; game position remains active.'));
  geolocation.getCurrentPosition(({coords})=>resolve({latitude:coords.latitude,longitude:coords.longitude,accuracy:coords.accuracy,x:p.x,z:p.z}),()=>reject(Error('Location unavailable; game position remains active.')),{enableHighAccuracy:true,timeout:10000,maximumAge:60000});
 });
}
