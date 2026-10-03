// A 270-degree parallel twin: unequal 270/450-degree firing intervals.
// Procedural combustion excitation, exhaust resonances, intake, wind and tire layers.
class TwinEngine extends AudioWorkletProcessor{
 constructor(){super();this.phase=0;this.rpm=1300;this.load=0;this.speed=0;this.cut=0;this.slip=0;this.cam=0;this.target={rpm:1300,load:0,speed:0,cut:0,slip:0,cam:0};this.pulse=0;this.exhaust=0;this.low=0;this.air=0;this.res=0;this.resV=0;this.seed=521;this.port.onmessage=e=>Object.assign(this.target,e.data)}
 noise(){this.seed=(Math.imul(this.seed,1664525)+1013904223)|0;return this.seed/2147483648}
 process(inputs,outputs){const out=outputs[0];if(!out?.length)return true;for(let i=0;i<out[0].length;i++){
 this.rpm+=(this.target.rpm-this.rpm)*.002;this.load+=(this.target.load-this.load)*.002;this.speed+=(this.target.speed-this.speed)*.002;const before=this.phase;this.phase+=this.rpm/(120*sampleRate);let fire=false;if(before<.375&&this.phase>=.375)fire=true;if(this.phase>=1){this.phase-=1;fire=true}const noise=this.noise();if(fire&&!this.target.cut)this.pulse+=.65+this.load*.65+noise*.08;
 this.pulse*=Math.exp(-1/(sampleRate*(.003+this.load*.004)));const excitation=this.pulse*(.7+noise*.3);this.exhaust+=(excitation-this.exhaust)*(.07+this.load*.12);this.low+=(this.exhaust-this.low)*.018;const engine=(this.exhaust-this.low)*1.8;
 // Resonant exhaust body; damped oscillator remains stable at all sample rates.
 const omega=2*Math.PI*105/sampleRate;this.resV+=(engine-this.res)*omega*omega-this.resV*omega*.22;this.res+=this.resV;
 this.air+=(noise-this.air)*.08;const wind=this.air*Math.min(.35,this.speed*this.speed*.000075);const tire=noise*this.target.slip*.07;const intake=(noise-this.air)*this.load*.025*(this.target.cam>1?1.6:.5);const sample=Math.tanh(engine*.48+this.res*.65+wind+intake+tire)*.32;
 for(const channel of out)channel[i]=sample;
 }return true}
}
registerProcessor('twin-engine',TwinEngine);
