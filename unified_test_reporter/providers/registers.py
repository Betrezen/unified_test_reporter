import pkg_resources

class TestReporterModule(object):

    def __init__(self, register, name, config):
        super(TestReporterModule, self).__init__()
        self.register = register
        self.name = name
        self.config = config
        self.module_init()
        self.enabled = True

    def module_init(self):
        pass

    @property
    def conf(self):
        return self.conf

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def __repr__(self):
        return '<{self.__class__.__name__} name=\'{self.name}\', enabled={self.enabled}>'.format(self=self)

class Register(list):

    modules = {}
    _loaded_modules = False

    @classmethod
    def register(cls, name):
        """ Decorator to register modules
        """
        def decorator(module_cls):
            cls.register_module(name, module_cls)
            return module_cls
        return decorator

    @classmethod
    def register_module(cls, name, module_cls):
        if issubclass(module_cls, TestReporterModule):
            cls.modules[name] = module_cls
            print ("register_module = {}".format(name))
        else:
            raise Exception('modules should be subclass of TestReporterModule')

    @classmethod
    def load_modules(cls):
        if cls._loaded_modules:
            return
        # Load modules
        for plugin in pkg_resources.iter_entry_points('unified_test_reporter.modules'):
            try:
                mcls = plugin.load()
                print ("load_modules = {}".format(plugin.name))
            except Exception as e:
                print ('Unable to load plugin "{}" - {}'.format(plugin.name, e))
                continue

            print ("pa:{}".format(mcls.__subclasses__()))
            if not issubclass(mcls, TestReporterModule):
                print ('plugin "{}" is not a subclass of TestReporterModule.'.format(plugin.name))
                continue
            cls.register_module(plugin.name, mcls)
        cls._loaded_modules = True

    def __init__(self, modules=None, config=None):
        list.__init__(self)
        self.config = config
        self.load_modules()

    def create_module(self, name):
        print self.modules
        print self.config.get(name, {})
        return self.modules.get(name)(self, name, self.config.get(name, {}))

    def get_module_by_name(self, name):
        for m in self:
            if m.name == name:
                return m

    def method_as_module(self, fn):
        module_cls = type('MethodModule', (TestReporterModule, ), {'process': staticmethod(fn)})
        return module_cls(self, fn.__name__, self.config.get('', {}))
