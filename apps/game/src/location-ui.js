const response = await fetch('/assets/compact-world.json');
if (response.ok) {
 const world = await response.json();
 if (world.locationName) {
  const city = world.locationName;
  const district = world.districtName || city;
  const road = world.primaryRoadName || 'Local roads';
  document.title = `${district} Ride - ${road}`;
  const brand = document.querySelector('.brand');
  if (brand?.firstChild) brand.firstChild.textContent = `${city.toUpperCase()} `;
  const location = document.querySelector('.location');
  if (location) location.textContent = `${district.toUpperCase()}, MICHIGAN · ${(world.regionName || '').toUpperCase()}`;
  const eyebrow = document.querySelector('#intro .eyebrow');
  if (eyebrow) eyebrow.textContent = `${city.toUpperCase()} / FREE RIDE`;
  const intro = document.querySelector('#intro p');
  if (intro) intro.textContent = `Ride ${road} through ${district}, Michigan.`;
  const spawn = document.querySelector('#spawn');
  if (spawn?.options.length) spawn.options[0].textContent = road;
  if (spawn?.options.length > 1) spawn.options[1].textContent = world.freewayName || 'Regional freeway';
  if (spawn && world.freewayName === road) spawn.querySelector('option[value="1"]')?.remove();
  world.businesses?.forEach((business,index)=>{
   if (!spawn || spawn.querySelector(`option[value="${10+index}"]`)) return;
   const option=document.createElement('option');option.value=10+index;option.textContent=business.name;spawn.append(option);
  });

  const updateLabels = () => {
   const bottom = document.querySelector('#bottomlabel');
   if (bottom && /Hall Road|M.?53/.test(bottom.textContent)) bottom.textContent = `${road.toUpperCase()} · ${city.toUpperCase()}`;
   const roadName = document.querySelector('#roadname');
   if (roadName?.textContent === 'SHELBY TOWNSHIP') roadName.textContent = city.toUpperCase();
   const progress = document.querySelector('#loadlabel');
   if (progress?.textContent === 'Building Shelby Township') progress.textContent = `Building ${city}`;
  };
  updateLabels();
  new MutationObserver(updateLabels).observe(document.querySelector('#app'), {childList: true, characterData: true, subtree: true});
 }
}
