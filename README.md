# CXC — Gastos de Cobranza

Pipeline automatizado que calcula el **gasto de cobranza** a cargar a los asociados con cartera de crédito vencida, y genera los archivos de cargue al sistema **Taylor** junto con el histórico detallado del período.

El proceso se ejecuta por **corte** (cada 5 días calendario aprox.) contra el Data Warehouse **GCC**, aplica reglas de elegibilidad y exclusión, calcula el gasto según tramos de mora, distribuye lo ya facturado, y exporta los resultados a Excel en una ruta de red compartida.

---

## Tabla de contenido

- [Idea general del negocio](#idea-general-del-negocio)
- [Arquitectura modular](#arquitectura-modular)
- [Flujo del pipeline](#flujo-del-pipeline-mainpy)
- [Módulos](#módulos)
  - [src/conexion](#srcconexion)
  - [src/validacion](#srcvalidacion)
  - [src/extraccion](#srcextraccion)
  - [src/transformacion](#srctransformacion)
  - [src/generacion](#srcgeneracion)
  - [src/utils](#srcutils)
- [Configuración](#configuración)
- [Variables de entorno](#variables-de-entorno)
- [Estructura de datos (`data/`)](#estructura-de-datos-data)
- [Excepciones y manejo de errores](#excepciones-y-manejo-de-errores)
- [Instalación](#instalación)
- [Ejecución](#ejecución)
- [Tests](#tests)
- [Notas y desviaciones conocidas](#notas-y-desviaciones-conocidas)

---

## Idea general del negocio

Coomeva cobra a los asociados en mora un "gasto de cobranza" proporcional al monto vencido, en función de cuántos días lleva en mora (tramo). Ese gasto:

- **No aplica** a todos los asociados: se excluyen los que están en procesos jurídicos/insolvencia, los fallecidos, los que ya no están en un estado de crédito válido, y los que no fueron asignados a la sub-campaña de cobranza (`PROCOBAS`).
- **Se descuenta** lo que el asociado ya tiene facturado por el concepto `CXCCRED`, para no cobrar dos veces.
- **Se agrupa por cédula**: aunque un asociado tenga varios créditos vencidos, el cargue a Taylor es uno solo por cédula, prorrateando el gasto entre sus créditos según su participación.
- **Se reporta dos veces**: un archivo de cargue a Taylor (agregado por cédula) y un histórico detallado (a nivel de crédito) que se consolida mensualmente.

## Arquitectura modular

El proyecto está deliberadamente separado por **etapa del pipeline**, no por tipo técnico. Cada carpeta bajo `src/` representa una responsabilidad de negocio independiente, con su propia función orquestadora (`run_*` / `extraer_*` / `filtrar_*`) que `main.py` invoca en secuencia. Los módulos no se llaman entre sí salvo para compartir `conexion` y `utils`:

```
main.py                    ← orquestador general (los 10 pasos del corte)
│
├── src/validacion/         Reglas de negocio de "puede correr el proceso hoy?"
│   ├── validar_gcc_actualizado.py   valida que el DW esté al día
│   └── scheduler.py                 determina si hoy hay un corte programado
│
├── src/conexion/           Acceso a datos (única puerta de entrada al DW)
│   └── gcc_client.py                conexión ODBC + ejecución de queries .sql
│
├── src/extraccion/         Extrae y persiste crudo (data/raw/)
│   ├── cartera.py                   cartera vencida (query SQL)
│   └── exepcions.py                 jurídicos, fallecidos y asignación
│
├── src/transformacion/     Filtra y calcula (data/elegibles/, data/calculado/)
│   ├── elegibles.py                 aplica reglas de exclusión
│   └── calculo.py                   tramos de mora, gastos, participación, facturado
│
├── src/generacion/         Genera los entregables finales (Excel a red compartida)
│   ├── taylor.py                    cargue Taylor (vigentes + retirados)
│   └── detallado.py                 histórico consolidado del período
│
└── src/utils/              Transversal a todos los módulos
    ├── load_config.py               lee config/config.yaml
    ├── helpers.py                   tipos de datos, logging de pasos
    └── excepciones.py               jerarquía de excepciones de negocio
```

**Por qué esta separación:** cada carpeta puede evolucionar, probarse o incluso re-ejecutarse de forma aislada — por ejemplo, `transformacion.calculo` puede volver a correr sobre un `data/raw` ya extraído sin tocar la capa de conexión, y `conexion.gcc_client` es el único lugar que sabe cómo hablar con el DW. La configuración (montos, rutas, calendarios) vive fuera del código en `config/`, así que ajustar un porcentaje de tramo o una ruta de red no requiere tocar Python.

## Flujo del pipeline (`main.py`)

`main.py` ejecuta 10 pasos secuenciales dentro de un único `try/except`; si un paso crítico falla, el proceso se detiene (`sys.exit(1)`):

| # | Paso | Función | Qué hace |
|---|------|---------|----------|
| 1 | Validar actualización DW | `validar_gcc_actualizado` | Compara la última fecha de carga del DW GCC contra hoy. Si no está al día, aborta (`GCCNoActualizadoError`). |
| 2 | Determinar corte programado | `schedule_task` | Lee `config/scheduler_corte.json` y busca si hoy corresponde a un corte. Si no hay ninguno, aborta (`CorteNoProgramadoError`). |
| 3 | Extraer cartera vencida | `extraer_cartera` | Ejecuta `sql/cartera_vencida.sql` contra el DW y persiste `data/raw/{periodo}/cartera_{fecha}.parquet`. |
| 4 | Extraer excepciones jurídicas | `extrac_excepcions` | Lee el último `.xlsx` de la ruta de jurídicos/insolvencias y lo guarda como `.csv`. |
| 5 | Extraer fallecidos | `extract_estados_fallecidos` | Ejecuta `sql/estados_fallecidos.sql` y guarda los estados como `.json`. |
| 6 | Extraer asignación | `extract_asignacion` | Lee el último `.xlsx` de asignación (qué cédulas están en qué sub-campaña) y lo guarda como `.csv`. |
| 7 | Filtrar elegibles | `filtrar_elegibles` | Aplica las 5 reglas de exclusión (ver [transformacion.elegibles](#srctransformacion)) y exporta `data/elegibles/`. |
| 8 | Calcular gastos | `run_calculos` | Asigna tramo de mora, calcula gasto proyectado, participación por crédito, descuenta lo facturado, y exporta `data/calculado/`. |
| 9 | Generar salida Taylor | `run_taylor` | Agrupa por cédula, separa retirados/excluidos, exporta 2 Excel a la ruta compartida. |
| 10 | Consolidar histórico | `run_detallado` | Concatena todos los `.parquet` de `data/calculado/{periodo}/` y exporta el histórico Excel del período. |

**Caso especial "corte 30":** si el código de corte termina en `30` (el último corte del mes), el período efectivo de reporte se desplaza al mes siguiente por convención contable (`main.py` líneas 35-40). Esto afecta en qué carpeta de `data/` y con qué nombre de período se guarda todo lo que sigue.

## Módulos

### `src/conexion`

Única capa que sabe hablar con el Data Warehouse GCC (Oracle, vía `pyodbc`). Expone:

- `ejecutar_query(query: str | Path) -> pd.DataFrame`: lee un archivo `.sql`, abre conexión con la cadena de la variable de entorno `GCC_CON`, ejecuta y cierra la conexión siempre (bloque `finally`).

Cualquier otro módulo que necesite datos del DW pasa por aquí — nadie abre su propia conexión ODBC.

### `src/validacion`

Guardas de entrada del proceso, se ejecutan **antes** de tocar datos:

- `validar_gcc_actualizado(val_gcc)`: corre la query de `config.yaml → queries.validacion_actualizacion` y compara la fecha máxima de carga contra hoy.
- `schedule_task()`: lee `config/scheduler_corte.json` (calendario de cortes de todo el año) y retorna las tareas cuya `fecha_proceso` es hoy.

### `src/extraccion`

Trae datos crudos desde 3 orígenes distintos y los normaliza a `data/raw/{periodo}/`:

- `cartera.py → extraer_cartera`: cartera vencida desde el DW (SQL), castea tipos según `config/data_types.json`.
- `exepcions.py`:
  - `extrac_excepcions`: cédulas en procesos jurídicos/insolvencia (Excel en ruta de red).
  - `extract_estados_fallecidos`: estados de fallecidos (SQL).
  - `extract_asignacion`: asignación de cédulas a sub-campañas de cobranza (Excel en ruta de red).

### `src/transformacion`

El corazón de la lógica de negocio.

**`elegibles.py`** filtra la cartera cruda aplicando, en orden:
1. Solo el corte programado para hoy (`CORTE`).
2. Mínimo 30 días de mora (`DIAS_MORA > 30`).
3. Estado de crédito no excluido (`config.yaml → params.estados_excluidos`, ej. `CASTIGADO`).
4. Cédula no está en jurídicos ni en fallecidos.
5. Cédula sí está asignada a alguna sub-campaña configurada (`config.yaml → params.subcampannas`).

**`calculo.py`** ejecuta 6 pasos sobre los elegibles (`run_calculos`):
1. `build_tramos`: asigna `TRAMO_MORA` según `config/tramos_mora.json`.
2. `calcular_gastos`: gasto proyectado = `VALOR_VENCIDO × porcentaje del tramo` (redondeado hacia abajo).
3. `calcular_participacion`: % que representa cada crédito dentro del gasto total de su cédula.
4. `distribuir_facturado`: prorratea lo ya facturado (`VALOR_FACTURADO_CXCRED`, que viene a nivel de cédula) entre los créditos según su participación, y calcula el gasto neto real (nunca negativo).
5. `build_hist_detallado`: agrega columnas de contexto (`PERIODO`, `FECHA_PROCESO`, `FECHA_CORTE`) y selecciona las 19 columnas de salida.
6. `exportar_detallado`: persiste en `data/calculado/{periodo}/calculado_{fecha}.parquet`.

### `src/generacion`

Construye los entregables finales que salen a la ruta de red compartida (`config.yaml → paths.salida_compartida`):

- **`taylor.py → run_taylor`**: agrupa el calculado por cédula (un registro por cédula, `drop_duplicates`), arma las 7 columnas que espera Taylor (`CEDULA, NUMERO CUOTA, VALOR, FECHA CARGUE, CODIGO CONCEPTO, CODIGO SISTEMA, CARGUE`), valida que no falte ninguna (`ColumnasFaltantes`), y **separa** en dos archivos según el `ESTADO ASOCIADO` contenga alguna palabra de retiro (`Retirado`, `Retiro`, `Excluido`, `Expulsión`):
  - `Cargue_Taylor_CXCCRED_{fecha}.xlsx` (vigentes → sí se cargan a Taylor)
  - `Cargue_Taylor_Retirados_CXCCRED_{fecha}.xlsx` (retirados → se reportan pero no se cargan)
- **`detallado.py → run_detallado`**: concatena **todos** los `.parquet` del período en `data/calculado/{periodo}/` (es decir, todos los cortes de ese mes ya procesados), valida columnas y exporta `Historico_Detallado_{periodo}.xlsx` ordenado por `CORTE` y `CEDULA`.

### `src/utils`

Transversal, sin lógica de negocio propia:

- `load_config.py`: carga `config/config.yaml` a un `dict`.
- `helpers.py`: `extraer_tipos()` (lee `config/data_types.json`) y `print_step()` (logging de progreso en consola, formato `[n/10] mensaje`).
- `excepciones.py`: jerarquía de excepciones de negocio (ver [más abajo](#excepciones-y-manejo-de-errores)).

## Configuración

Todo lo parametrizable vive en `config/`, no en el código:

| Archivo | Contenido |
|---|---|
| `config.yaml` | Rutas a los `.sql` de queries, estados de crédito excluidos, sub-campañas válidas, y las 3 rutas de red (jurídicos, asignación, salida compartida). |
| `data_types.json` | Tipos de dato esperados por columna de la cartera cruda (`raw_data`), usados para castear al extraer. |
| `tramos_mora.json` | Definición de tramos de mora: código, días mín/máx y porcentaje de gasto de cada tramo (5 tramos, de 31 días hasta >150 días). |
| `scheduler_corte.json` | Calendario completo del año con cada corte (`codigo_corte`, `periodo`, `fecha_proceso`, `fecha_ejecucion`). `schedule_task()` filtra por la fecha de hoy. |
| `scheduler_cierre.json` | Calendario de fechas de cierre mensual (`periodo` → `fecha_cierre`); referencia para los cierres de mes. |

`config.yaml` está en `.gitignore` (junto con `config/` completo salvo lo que no aplique) porque contiene rutas de red específicas del entorno.

## Variables de entorno

El proyecto usa `python-dotenv` para cargar un `.env` en la raíz (también ignorado por git):

| Variable | Uso |
|---|---|
| `GCC_CON` | Cadena de conexión ODBC (driver Oracle Instant Client) hacia el DW GCC. Consumida únicamente por `src/conexion/gcc_client.py`. |

> El `.env` contiene credenciales reales de conexión — nunca debe commitearse ni compartirse fuera del repositorio local.

## Estructura de datos (`data/`)

Toda la data intermedia se organiza por **período** (`YYYY-MM`) y se regenera en cada corrida — no se versiona (está en `.gitignore`):

```
data/
├── raw/{periodo}/
│   ├── cartera_{fecha_proceso}.parquet          ← cartera vencida cruda
│   └── excepcions/
│       ├── excepcions_{fecha}.csv               ← jurídicos/insolvencia
│       ├── fallecidos_{fecha}.json              ← estados de fallecidos
│       └── asignacion_{fecha}.csv               ← asignación a sub-campañas
├── elegibles/{periodo}/
│   └── elegibles_{fecha_proceso}.parquet        ← cartera ya filtrada
└── calculado/{periodo}/
    └── calculado_{fecha_proceso}.parquet        ← gasto ya calculado por crédito
```

Los entregables finales (Excel de Taylor y el histórico detallado) **no** se guardan en `data/`, sino directamente en la ruta de red de `config.yaml → paths.salida_compartida`, bajo `{periodo}/taylor/` y `{periodo}/detallado/` respectivamente.

## Excepciones y manejo de errores

`src/utils/excepciones.py` define una jerarquía plana de excepciones de negocio. `main.py` las captura una por una con manejo distinto:

| Excepción | Se lanza cuando… | Detiene el proceso (`sys.exit(1)`) |
|---|---|---|
| `GCCConexionError` | Falla la conexión ODBC al DW | Sí (vía otras excepciones que la envuelven) |
| `GCCNoActualizadoError` | El DW no tiene datos del día de hoy | Sí |
| `CorteNoProgramadoError` | No hay corte agendado para hoy en `scheduler_corte.json` | Sí |
| `TipoNoCompatible` | Un tipo de dato de la cartera no castea según `data_types.json` | Sí |
| `ColumnasFaltantes` | Falta una columna requerida (Taylor o histórico detallado) | **No** — solo se imprime el error |
| `ErrorExportandoArchivo` | Falla la escritura de un Excel de salida | **No** — solo se imprime el error |

`FileNotFoundError` y `ValueError` genéricos también se capturan explícitamente y sí detienen el proceso. Cualquier otra excepción no prevista cae en el `except Exception` final.

## Instalación

```bash
python -m venv .venv313
.venv313\Scripts\activate        # Windows
pip install -r requirements.txt
```

Dependencias principales: `pandas`, `pyarrow`, `pyodbc`, `openpyxl`, `PyYAML`, `python-dotenv`, `numpy`. Se necesita además el driver ODBC de Oracle Instant Client instalado y configurado en el sistema (referenciado en `GCC_CON`).

Copiar las plantillas de ejemplo y completarlas con los valores reales del entorno:

```bash
cp .env.example .env
cp config/config.example.yaml config/config.yaml
```

Ver [Variables de entorno](#variables-de-entorno) y [Configuración](#configuración) para el detalle de cada clave.

## Ejecución

```bash
python main.py
```

El proceso solo avanza si:
1. El DW GCC tiene datos de hoy, **y**
2. Hoy corresponde a un corte programado en `config/scheduler_corte.json`.

Si ambas condiciones se cumplen, corre los 10 pasos descritos arriba sin intervención manual.

## Tests

`test/main.py` es una copia reducida del pipeline (pasos 1 a 8: hasta `run_calculos`) usada para pruebas manuales del flujo de extracción/cálculo sin llegar a generar los entregables finales en la ruta compartida. No es una suite de `pytest` con aserciones — es un script ejecutable equivalente a un "modo dry-run" del proceso completo.

## Notas y desviaciones conocidas

- `docs/repo_structure.txt` es un documento de planeación temprano del proyecto; ya no refleja la estructura real (menciona `src/calculo/` y `src/generacion/cierre.py`, que terminaron consolidados como `src/transformacion/calculo.py`, y la salida Taylor vive en `src/generacion/taylor.py`). Tómese como contexto histórico, no como referencia de estructura actual.
- `ColumnasFaltantes` y `ErrorExportandoArchivo` no detienen el proceso con código de salida distinto de 0 en `main.py` — quedan solo como mensaje en consola, a diferencia del resto de excepciones de negocio.
