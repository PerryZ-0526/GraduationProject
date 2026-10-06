"""常驻子进程执行原生布尔；原生断言不能终止材料账本和其他路线。"""
import multiprocessing


class BatchBooleanFailure(RuntimeError):pass


def serve(connection):
    from geogram_batch_memory import GeogramBatchMemory
    api=GeogramBatchMemory();connection.send(('ready',None))
    try:
        while True:
            request=connection.recv()
            if request is None:return
            try:connection.send(('result',api.difference_batch(*request,certified_operands=True)))
            except Exception as error:connection.send(('error',repr(error)))
    except EOFError:return
    finally:connection.close()


class BatchBooleanService:
    def __init__(self):
        context=multiprocessing.get_context('spawn');self.connection,child=context.Pipe()
        # 独立启动避免继承已经初始化的CUDA上下文，布尔子进程只运行CPU原生库。
        self.process=context.Process(target=serve,args=(child,));self.process.start();child.close()
        if self.connection.recv()[0]!='ready':raise RuntimeError('布尔子进程未就绪')

    def difference_batch(self,vertices,faces,tools,certified_operands=True):
        if not certified_operands:raise ValueError('批量服务必须由调用方认证全部闭合操作数')
        try:
            self.connection.send((vertices,faces,tools));kind,value=self.connection.recv()
        except (EOFError,BrokenPipeError,ConnectionResetError) as error:
            self.process.join(timeout=2)
            raise BatchBooleanFailure(f'原生布尔进程退出，pid={self.process.pid}，exit_code={self.process.exitcode}') from error
        if kind!='result':raise BatchBooleanFailure('原生布尔执行异常：'+str(value))
        value[3]['worker_pid']=self.process.pid
        return value

    def close(self):
        if self.process.is_alive():
            try:self.connection.send(None)
            except (EOFError,BrokenPipeError):pass
            self.process.join(timeout=2)
        if self.process.is_alive():
            # 仅回收本服务创建且已要求退出的子进程，不触碰共享实例上的其他任务。
            self.process.terminate();self.process.join(timeout=2)
        self.connection.close()
