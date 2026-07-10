const DEMO_TOPICS=['Тревога','Панические атаки','Невроз','ВСД','Самопомощь','Работа с мыслями'];
const DEMO_DAYS=['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];
const isoDate=daysAgo=>{const d=new Date('2026-07-10T00:00:00Z');d.setUTCDate(d.getUTCDate()-daysAgo);return d.toISOString().slice(0,10)};
const makeRow=(type,index,daysAgo,topic)=>{
  const shorts=type==='Shorts';
  const views=(shorts?12000:6500)+index*(shorts?3100:1900);
  const duration=shorts?34+(index%5)*5:720+(index%6)*150;
  return {
    id:`demo-${type.toLowerCase()}-${index}`,
    title:`Демонстрационный материал ${index+1}: ${topic}`,
    type,
    published:isoDate(daysAgo),
    duration,
    impressions:Math.round(views*(shorts?1.8:13)),
    ctr:shorts?4.2+(index%4)*.35:3.7+(index%5)*.42,
    views,
    avgView:Math.round(duration*(shorts?.78:.47)),
    watchHours:Math.round(views*duration*(shorts?.78:.47)/3600),
    topic,
    retention:shorts?.72+(index%5)*.025:.39+(index%5)*.035,
    weekday:DEMO_DAYS[(6-daysAgo%7+7)%7],
    ageDays:daysAgo,
    momentum:views/Math.max(daysAgo,10),
    subscribers:Math.round(views*(shorts?.0026:.0061)),
    fresh:daysAgo<=90
  };
};

const shorts365=Array.from({length:18},(_,i)=>makeRow('Shorts',i,18+i*17,DEMO_TOPICS[i%DEMO_TOPICS.length]));
const videos365=Array.from({length:12},(_,i)=>makeRow('Видео',i,24+i*25,DEMO_TOPICS[i%DEMO_TOPICS.length]));
const content90=[
  ...shorts365.filter(x=>x.fresh),
  ...videos365.filter(x=>x.fresh),
  ...Array.from({length:16},(_,i)=>makeRow(i%4===0?'Видео':'Shorts',40+i,3+i*4,DEMO_TOPICS[i%DEMO_TOPICS.length]))
];

window.YT_DATA={
  meta:{channel:'Павел Федоренко (@pavelfdrk)',asOf:'2026-07-10',subscribers:204000,period365:'Демонстрационный период',period90:'Последние 90 дней',source:'Compliance review · обезличенные демонстрационные данные'},
  overview365:[
    {type:'Shorts',views:640000,watchHours:5100,avgView:'0:00:43'},
    {type:'Видео',views:220000,watchHours:18400,avgView:'0:07:12'},
    {type:'Записи',views:28000,watchHours:94,avgView:'0:00:21'},
    {type:'Прямые трансляции',views:9000,watchHours:1400,avgView:'0:12:40'}
  ],
  studio90:{views:180000,viewsDelta:'+18% к предыдущим 90 дням',watchHours:6200,watchDelta:'+9% к предыдущим 90 дням',subscribers:720,subscribersDelta:'+11% к предыдущим 90 дням'},
  weak:{videoCtr:4.54,shortsCtr:4.73,lowCtrShare:.28,videoRetention:.46,shortsRetention:.77,lowRetentionShare:.25,totalViews90:180000,freshViews90:126000,freshShare:.70,archiveViews90:54000,subscribers90:720,conversion:.004,freshSubscribers:520,freshSubscriberShare:.72,shortsConversion:.0026,videoConversion:.0061},
  videos365,
  shorts365,
  content90,
  recommendationLines:['Демонстрационная версия показывает структуру аналитики без публикации конфиденциальных данных канала.']
};
