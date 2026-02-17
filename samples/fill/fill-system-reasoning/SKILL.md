#SKILL.md

This is about how to interpret the user intent and decide which workloads should be deployed.

## Locate the right service

These are all the services FILL provides for their machines, each with a name of a short description.

```turtle
fill:Service1 intend:description "Service1 records all components and the process steps are analyzed. Occurred messages and the tool usage of each component are displayed and provide transparency in the production data.".
fill:Service2 intend:description "Service2 provides an overview of your production. The machine status can be called up at any time, allowing workflows to be optimized.".
fill:Service3 intend:description "Service3 monitors media consumption and ensures early detection of production changes and leaks that might otherwise go undetected.".
fill:Service4 intend:description "Service4 provides information on the utilization of a machine in a defined period. The analysis provides insights into utilization and efficiency and identifies any bottlenecks or optimization potential.".
fill:Service5 intend:description "Service5 records all alarms and messages and identifies the main messages. Actual machine problems can thus be identified.".
fill:Service6 intend:description "Service6 allows manual analysis of all recorded data. Any questions can thus be clarified independently.".
fill:Service7 intend:description "Service7 automatically records every NC program change. The possibility of analysis and tracking provides more transparency and control.".
fill:Service8 intend:description "Service8 analyzes the G-code of all components. Optimization potential is suggested to effectively reduce cycle time.".
fill:Service9 intend:description "Service9 detects the constant temperature range for efficient production. This saves time and reduces scrap due to a shorter warm-up phase.".
fill:Service10 intend:description "Service10 analyzes tool wear. You can determine the condition when replacing tools or compare wear among tools of the same type.".
fill:Service11 intend:description "Service11 logs component changes of motors, spindles and ball screws. In addition, every machine crash is recorded, including the program run.".
fill:Service12 intend:description "Service12 test runs generate the specific machine performance indicator. This allows you to detect changes over time and check successful installation after component replacement.".
```

## Find the components in the service

```turtle
fill:Service1 intend:hasComponent fill:Component1.
fill:Service1 intend:hasComponent fill:Component2.
fill:Service1 intend:hasComponent fill:Component3.
fill:Service1 intend:hasComponent fill:Component6.
fill:Service1 intend:hasComponent fill:Container30.
fill:Service1 intend:hasComponent fill:Component12.
fill:Service2 intend:hasComponent fill:Component4.
fill:Service3 intend:hasComponent fill:Component1.
fill:Service3 intend:hasComponent fill:Component4.
fill:Service3 intend:hasComponent fill:Component5.
fill:Service4 intend:hasComponent fill:Component1.
fill:Service4 intend:hasComponent fill:Component4.
fill:Service5 intend:hasComponent fill:Component6.
fill:Service7 intend:hasComponent fill:Component1.
fill:Service7 intend:hasComponent fill:Component2.
fill:Service7 intend:hasComponent fill:Component3.
fill:Service7 intend:hasComponent fill:Container30.
fill:Service8 intend:hasComponent fill:Component10.
fill:Service8 intend:hasComponent fill:Component11.
fill:Service10 intend:hasComponent fill:Component2.
fill:Service10 intend:hasComponent fill:Component3.
fill:Service10 intend:hasComponent fill:Component13.
fill:Service11 intend:hasComponent fill:Component4.
fill:Service11 intend:hasComponent fill:Container30.
fill:Service11 intend:hasComponent fill:Component8.
fill:Service11 intend:hasComponent fill:Component9.
fill:Service12 intend:hasComponent fill:Component8.
fill:Service12 intend:hasComponent fill:Component9.
```

## Finally, find the "containers" inside the component. 

The "container" here is the "workload" required as result of the reasoning task. Return the container name, without the prefix, e.g., return Container1 instead of fill:Container1

```
fill:Component1 intend:hasContainer fill:Container1.
fill:Component1 intend:hasContainer fill:Container2.
fill:Component1 intend:hasContainer fill:Container3.
fill:Component1 intend:hasContainer fill:Container4.
fill:Component1 intend:hasContainer fill:Container5.
fill:Component1 intend:hasContainer fill:Container6.
fill:Component1 intend:hasContainer fill:Container7.
fill:Component1 intend:hasContainer fill:Container8.
fill:Component1 intend:hasContainer fill:Container9.
fill:Component1 intend:hasContainer fill:Container10.
fill:Component2 intend:hasContainer fill:Container11.
fill:Component2 intend:hasContainer fill:Container12.
fill:Component2 intend:hasContainer fill:Container13.
fill:Component2 intend:hasContainer fill:Container14.
fill:Component2 intend:hasContainer fill:Container15.
fill:Component2 intend:hasContainer fill:Container16.
fill:Component3 intend:hasContainer fill:Container17.
fill:Component3 intend:hasContainer fill:Container18.
fill:Component12 intend:hasContainer fill:Container19.
fill:Component12 intend:hasContainer fill:Container20.
fill:Component13 intend:hasContainer fill:Container21.
fill:Component13 intend:hasContainer fill:Container22.
fill:Component4 intend:hasContainer fill:Container23.
fill:Component4 intend:hasContainer fill:Container24.
fill:Component5 intend:hasContainer fill:Container25.
fill:Component5 intend:hasContainer fill:Container26.
fill:Component5 intend:hasContainer fill:Container27.
fill:Component5 intend:hasContainer fill:Container28.
fill:Component6 intend:hasContainer fill:Container29.
fill:Container30 intend:hasContainer fill:Container30.
fill:Component10 intend:hasContainer fill:Container31.
fill:Component10 intend:hasContainer fill:Container32.
fill:Component10 intend:hasContainer fill:Container33.
fill:Component10 intend:hasContainer fill:Container34.
fill:Component10 intend:hasContainer fill:Container35.
fill:Component10 intend:hasContainer fill:Container36.
fill:Component10 intend:hasContainer fill:Container37.
fill:Component10 intend:hasContainer fill:Container38.
fill:Component11 intend:hasContainer fill:Container39.
fill:Component8 intend:hasContainer fill:Container40.
fill:Component8 intend:hasContainer fill:Container41.
fill:Component14 intend:hasContainer fill:Container42.
```